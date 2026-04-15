import os
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from mysql.connector import pooling
from dotenv import load_dotenv

import json
from decimal import Decimal
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

def serialize(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

load_dotenv()

app = FastAPI(title="SubBuddy API")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

db_pool = pooling.MySQLConnectionPool(
    pool_name="subbuddy_pool",
    pool_size=10,
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    database=os.getenv("DB_NAME")
)

def get_db_conn():
    return db_pool.get_connection()

# Generates 12 months of payment records from start_date
def generate_payments(cursor, sub_id, start_date, cost, freq):
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    payments = []
    current = start_date
    end_date = start_date + relativedelta(months=12)

    while current <= end_date:
        payments.append((sub_id, cost, current))
        if freq == 'Weekly':
            current += timedelta(weeks=1)
        elif freq == 'Monthly':
            current += relativedelta(months=1)
        elif freq == 'Quarterly':
            current += relativedelta(months=3)
        elif freq == 'Annually':
            current += relativedelta(years=1)
        else:
            break

    cursor.executemany(
        "INSERT INTO SUBSCRIPTION_PAYMENTS (SUB_ID, SUBPAY_Cost, SUBPAY_Date) VALUES (%s, %s, %s)",
        payments
    )


# --- LOGIN ---
@app.get("/")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})

@app.post("/")
def login(
    user_email: str = Form(...),
    user_password: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM USERS WHERE USER_Email = %s AND USER_Password = %s",
            (user_email, user_password)
        )
        user = cursor.fetchone()
        if user:
            return RedirectResponse(url=f"/{user['USER_ID']}/dashboard", status_code=303)
        else:
            return {"error": "Invalid email or password"}
    finally:
        cursor.close()
        conn.close()


# --- REGISTER ---
@app.post("/register")
def register(
    user_fname: str = Form(...),
    user_lname: str = Form(...),
    user_email: str = Form(...),
    user_password: str = Form(...),
    user_phone: str = Form(None)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO USERS (USER_FName, USER_LName, USER_Email, USER_Password, USER_Phone) VALUES (%s, %s, %s, %s, %s)",
            (user_fname, user_lname, user_email, user_password, user_phone)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- DASHBOARD ---
@app.get("/{user_id}/dashboard")
def dashboard(request: Request, user_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM USERS WHERE USER_ID = %s", (user_id,))
        user = cursor.fetchone()

        query = """
            SELECT S.SUB_ID, S.SUB_Name, S.SUB_SDate,
                   SP.SUBPAY_ID, SP.SUBPAY_Cost, SP.SUBPAY_Date, SP.SUBPAY_Status, S.SUB_CAT,
                   SV.SUBVER_FREQ
            FROM SUBSCRIPTIONS S
            JOIN SUBSCRIPTION_PAYMENTS SP ON S.SUB_ID = SP.SUB_ID
            JOIN SUBSCRIPTION_VERSIONS SV ON SV.SUBVER_ID = (
                SELECT SUBVER_ID FROM SUBSCRIPTION_VERSIONS
                WHERE SUB_ID = S.SUB_ID
                ORDER BY SUBVER_DateAdded DESC
                LIMIT 1
            )
            WHERE S.USER_ID = %s
            ORDER BY SP.SUBPAY_Date
        """
        cursor.execute(query, (user_id,))
        subscriptions = cursor.fetchall()

        subscriptions = json.loads(json.dumps(subscriptions, default=serialize))
        user = json.loads(json.dumps(user, default=serialize))

        cursor.execute("SELECT * FROM CATEGORIES WHERE USER_ID = %s", (user_id,))
        categories = cursor.fetchall()
        categories = json.loads(json.dumps(categories, default=serialize))

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={"user": user, "subscriptions": subscriptions, "categories": categories}
        )
    finally:
        cursor.close()
        conn.close()


# --- ADD SUBSCRIPTION ---
@app.post("/add-subscription")
def add_subscription(
    user_id: int = Form(...),
    sub_name: str = Form(...),
    sub_cat: str = Form(None),
    sub_sdate: str = Form(...),
    subver_cost: float = Form(...),
    subver_freq: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO SUBSCRIPTIONS (USER_ID, SUB_Name, SUB_CAT, SUB_SDate) VALUES (%s, %s, %s, %s)",
            (user_id, sub_name, sub_cat, sub_sdate)
        )
        sub_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO SUBSCRIPTION_VERSIONS (SUB_ID, SUBVER_Cost, SUBVER_FREQ, SUBVER_EffectiveDate) VALUES (%s, %s, %s, %s)",
            (sub_id, subver_cost, subver_freq, sub_sdate)
        )
        generate_payments(cursor, sub_id, sub_sdate, subver_cost, subver_freq)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)


# --- UPDATE SUBSCRIPTION (name, category, cost, freq) ---
@app.post("/update-subscription")
def update_subscription(
    user_id: int = Form(...),
    sub_id: int = Form(...),
    sub_name: str = Form(...),
    sub_cat: str = Form(None),
    subver_cost: float = Form(...),
    subver_freq: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE SUBSCRIPTIONS SET SUB_Name = %s, SUB_CAT = %s WHERE SUB_ID = %s",
            (sub_name, sub_cat, sub_id)
        )
        cursor.execute(
            "INSERT INTO SUBSCRIPTION_VERSIONS (SUB_ID, SUBVER_Cost, SUBVER_FREQ, SUBVER_EffectiveDate) VALUES (%s, %s, %s, CURDATE())",
            (sub_id, subver_cost, subver_freq)
        )
        cursor.execute(
            "DELETE FROM SUBSCRIPTION_PAYMENTS WHERE SUB_ID = %s AND SUBPAY_Date > CURDATE() AND SUBPAY_Status != 'Cancelled'",
            (sub_id,)
        )
        generate_payments(cursor, sub_id, date.today() + timedelta(days=1), subver_cost, subver_freq)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)


# --- UPDATE SINGLE PAYMENT ---
@app.post("/update-payment")
def update_payment(
    user_id: int = Form(...),
    subpay_id: int = Form(...),
    subpay_cost: float = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE SUBSCRIPTION_PAYMENTS SET SUBPAY_Cost = %s WHERE SUBPAY_ID = %s",
            (subpay_cost, subpay_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)


# --- CANCEL SUBSCRIPTION ---
@app.post("/cancel-subscription")
def cancel_subscription(
    sub_id: int = Form(...),
    user_id: int = Form(...),
    cancel_date: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM SUBSCRIPTION_PAYMENTS WHERE SUB_ID = %s AND SUBPAY_Date > %s",
            (sub_id, cancel_date)
        )
        cursor.execute(
            "UPDATE SUBSCRIPTION_PAYMENTS SET SUBPAY_Status = 'Cancelled' WHERE SUB_ID = %s AND SUBPAY_Date = %s",
            (sub_id, cancel_date)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)



# --- ADD CUSTOM CATEGORY ---
@app.post("/add-category")
def add_category(
    cat_name: str = Form(...),
    user_id: int = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO CATEGORIES (CAT_Name, USER_ID) VALUES (%s, %s)",
            (cat_name, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return {"status": "ok"}


# --- DELETE CUSTOM CATEGORY ---
@app.post("/delete-category")
def delete_category(cat_id: int = Form(...), user_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM CATEGORIES WHERE CAT_ID = %s AND USER_ID = %s",
            (cat_id, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)\
    

# --- PAUSE SUBSCRIPTION ---
@app.post("/pause-subscription")
def pause_subscription(sub_id: int = Form(...), user_id: int = Form(...), pause_date: str = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE SUBSCRIPTION_PAYMENTS SET SUBPAY_Status = 'Paused' WHERE SUB_ID = %s AND SUBPAY_Date >= %s AND SUBPAY_Status = 'Active'",
            (sub_id, pause_date)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)


# --- RESUME SUBSCRIPTION ---
@app.post("/resume-subscription")
def resume_subscription(sub_id: int = Form(...), user_id: int = Form(...), resume_date: str = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE SUBSCRIPTION_PAYMENTS SET SUBPAY_Status = 'Active' WHERE SUB_ID = %s AND SUBPAY_Date >= %s AND SUBPAY_Status = 'Paused'",
            (sub_id, resume_date)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)





# --- FAMILY PAGE ---
@app.get("/{user_id}/family")
def family_page(request: Request, user_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        # Get the family this user manages
        cursor.execute("""
            SELECT F.* FROM FAMILIES F
            JOIN FAMILY_MANAGERS FM ON F.FAMMAN_ID = FM.FAMMAN_ID
            WHERE FM.USER_ID = %s
        """, (user_id,))
        family = cursor.fetchone()

        members = []
        family_subs = []
        if family:
            # Get members
            cursor.execute("""
                SELECT U.USER_ID, U.USER_FName, U.USER_LName, U.USER_Email
                FROM FAMILY_USERS FU
                JOIN USERS U ON FU.USER_ID = U.USER_ID
                WHERE FU.FAM_ID = %s
            """, (family['FAM_ID'],))
            members = cursor.fetchall()

            # Get all subscriptions for the family
            cursor.execute("""
                SELECT U.USER_ID, U.USER_FName, U.USER_LName,
                       S.SUB_ID, S.SUB_Name, S.SUB_CAT,
                       SP.SUBPAY_Cost, SP.SUBPAY_Date, SP.SUBPAY_Status,
                       SV.SUBVER_FREQ
                FROM FAMILY_USERS FU
                JOIN USERS U ON FU.USER_ID = U.USER_ID
                JOIN SUBSCRIPTIONS S ON U.USER_ID = S.USER_ID
                JOIN SUBSCRIPTION_PAYMENTS SP ON S.SUB_ID = SP.SUB_ID
                JOIN SUBSCRIPTION_VERSIONS SV ON SV.SUBVER_ID = (
                    SELECT SUBVER_ID FROM SUBSCRIPTION_VERSIONS
                    WHERE SUB_ID = S.SUB_ID
                    ORDER BY SUBVER_DateAdded DESC LIMIT 1
                )
                WHERE FU.FAM_ID = %s
                ORDER BY U.USER_LName, SP.SUBPAY_Date
            """, (family['FAM_ID'],))
            family_subs = cursor.fetchall()

        family = json.loads(json.dumps(family, default=serialize)) if family else None
        members = json.loads(json.dumps(members, default=serialize))
        family_subs = json.loads(json.dumps(family_subs, default=serialize))

        cursor.execute("SELECT * FROM USERS WHERE USER_ID = %s", (user_id,))
        user = cursor.fetchone()
        user = json.loads(json.dumps(user, default=serialize))

        return templates.TemplateResponse(
            request=request,
            name="family.html",
            context={"user": user, "family": family, "members": members, "family_subs": family_subs}
        )
    finally:
        cursor.close()
        conn.close()


# --- ADMIN PAGE ---
@app.get("/{user_id}/admin")
def admin_page(request: Request, user_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM USERS WHERE USER_ID = %s", (user_id,))
        user = cursor.fetchone()
        user = json.loads(json.dumps(user, default=serialize))

        cursor.execute("""
            SELECT F.FAM_ID, F.FAM_Name, F.FAM_SLimit,
                   U.USER_FName, U.USER_LName
            FROM FAMILIES F
            JOIN FAMILY_MANAGERS FM ON F.FAMMAN_ID = FM.FAMMAN_ID
            JOIN USERS U ON FM.USER_ID = U.USER_ID
        """)
        families = cursor.fetchall()
        families = json.loads(json.dumps(families, default=serialize))

        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={"user": user, "families": families}
        )
    finally:
        cursor.close()
        conn.close()


# --- ADMIN: SEARCH USER ---
@app.get("/admin/search")
def admin_search_user(request: Request, q: str):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM USERS
            WHERE USER_Email LIKE %s
            OR CONCAT(USER_FName, ' ', USER_LName) LIKE %s
        """, (f"%{q}%", f"%{q}%"))
        results = cursor.fetchall()
        results = json.loads(json.dumps(results, default=serialize))
        return {"users": results}
    finally:
        cursor.close()
        conn.close()


# --- ADMIN: CREATE FAMILY ---
@app.post("/admin/create-family")
def admin_create_family(
    user_id: int = Form(...),
    fam_name: str = Form(...),
    manager_email: str = Form(...),
    fam_slimit: float = Form(None)
):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT USER_ID FROM USERS WHERE USER_Email = %s", (manager_email,))
        user = cursor.fetchone()
        if not user:
            return {"error": "No user found with that email"}

        user_id = user['USER_ID']

        # Insert into FAMILY_MANAGERS if not already there
        cursor.execute("SELECT FAMMAN_ID FROM FAMILY_MANAGERS WHERE USER_ID = %s", (user_id,))
        manager = cursor.fetchone()
        if not manager:
            cursor.execute("INSERT INTO FAMILY_MANAGERS (USER_ID) VALUES (%s)", (user_id,))
            famman_id = cursor.lastrowid
        else:
            famman_id = manager['FAMMAN_ID']

        # Check if this manager already manages a family
        cursor.execute("SELECT FAM_ID FROM FAMILIES WHERE FAMMAN_ID = %s", (famman_id,))
        if cursor.fetchone():
            return {"error": "This user already manages a family"}

        cursor.execute(
            "INSERT INTO FAMILIES (FAM_Name, FAMMAN_ID, FAM_SLimit) VALUES (%s, %s, %s)",
            (fam_name, famman_id, fam_slimit)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/admin", status_code=303)



# --- ADMIN: REASSIGN FAMILY MANAGER ---
@app.post("/admin/reassign-family-manager")
def reassign_family_manager(
    user_id: int = Form(...),
    fam_id: int = Form(...),
    manager_email: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT USER_ID FROM USERS WHERE USER_Email = %s", (manager_email,))
        user = cursor.fetchone()
        if not user:
            return {"error": "No user found with that email"}

        user_id = user['USER_ID']

        # Insert into FAMILY_MANAGERS if not already there
        cursor.execute("SELECT FAMMAN_ID FROM FAMILY_MANAGERS WHERE USER_ID = %s", (user_id,))
        manager = cursor.fetchone()
        if not manager:
            cursor.execute("INSERT INTO FAMILY_MANAGERS (USER_ID) VALUES (%s)", (user_id,))
            famman_id = cursor.lastrowid
        else:
            famman_id = manager['FAMMAN_ID']

        # Check if this manager already manages a family
        cursor.execute("SELECT FAM_ID FROM FAMILIES WHERE FAMMAN_ID = %s AND FAM_ID != %s", (famman_id, fam_id))
        if cursor.fetchone():
            return {"error": "This user already manages another family"}

        cursor.execute("UPDATE FAMILIES SET FAMMAN_ID = %s WHERE FAM_ID = %s", (famman_id, fam_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/admin", status_code=303)



# --- ADMIN: GET USER SUBSCRIPTIONS ---
@app.get("/admin/user/{user_id}/subs")
def admin_get_user_subs(user_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT S.SUB_ID, S.SUB_Name, S.SUB_CAT,
                   SP.SUBPAY_ID, SP.SUBPAY_Cost, SP.SUBPAY_Date, SP.SUBPAY_Status,
                   SV.SUBVER_FREQ
            FROM SUBSCRIPTIONS S
            JOIN SUBSCRIPTION_PAYMENTS SP ON S.SUB_ID = SP.SUB_ID
            JOIN SUBSCRIPTION_VERSIONS SV ON SV.SUBVER_ID = (
                SELECT SUBVER_ID FROM SUBSCRIPTION_VERSIONS
                WHERE SUB_ID = S.SUB_ID
                ORDER BY SUBVER_DateAdded DESC LIMIT 1
            )
            WHERE S.USER_ID = %s
            ORDER BY SP.SUBPAY_Date DESC
        """, (user_id,))
        subs = cursor.fetchall()
        subs = json.loads(json.dumps(subs, default=serialize))
        return {"subscriptions": subs}
    finally:
        cursor.close()
        conn.close()



# --- ADMIN: Dissolve Family ---
@app.post("/admin/dissolve-family")
def dissolve_family(fam_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM FAMILY_USERS WHERE FAM_ID = %s", (fam_id,))
        cursor.execute("DELETE FROM FAMILIES WHERE FAM_ID = %s", (fam_id,))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        return {"status": "error"}
    finally:
        cursor.close()
        conn.close()


# --- ADMIN: UPDATE USER ---
@app.post("/admin/update-user")
def admin_update_user(
    user_id: int = Form(...),
    user_fname: str = Form(...),
    user_lname: str = Form(...),
    user_email: str = Form(...),
    user_phone: str = Form(None)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE USERS SET USER_FName = %s, USER_LName = %s, USER_Email = %s, USER_Phone = %s WHERE USER_ID = %s",
            (user_fname, user_lname, user_email, user_phone, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)
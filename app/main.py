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
    pool_name="subbuddy_pool", pool_size=10,
    host=os.getenv("DB_HOST"), user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"), database=os.getenv("DB_NAME")
)

def get_db_conn():
    return db_pool.get_connection()

def is_admin(cursor, user_id: int) -> bool:
    cursor.execute("SELECT * FROM SYSTEM_ADMINS WHERE USER_ID = %s", (user_id,))
    return cursor.fetchone() is not None




# Helper method that generates 12 months of payment records from start_date
def generate_payments(cursor, sub_id, start_date, cost, freq):
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    payments = []
    current = start_date
    end_date = start_date + relativedelta(months=12)

    while current < end_date:
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

# ==================== LOGIN / REGISTER ===================== #

# --- GET LOGIN PAGE---
@app.get("/")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})


# --- POST LOGIN ---
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


# --- POST REGISTER ---
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



# ==================== DASHBOARD ===================== #

# ---GET DASHBOARD ---
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

        cursor.execute("""
            SELECT F.FAM_Name, F.FAM_SLimit, F.FAM_ID
            FROM FAMILY_USERS FU
            JOIN FAMILIES F ON FU.FAM_ID = F.FAM_ID
            WHERE FU.USER_ID = %s
        """, (user_id,))
        family = cursor.fetchone()
        family = json.loads(json.dumps(family, default=serialize)) if family else None

        cursor.execute("SELECT * FROM FAMILY_MANAGERS WHERE USER_ID = %s", (user_id,))
        is_manager = cursor.fetchone() is not None

        print("FAMILY:", family)
        print("IS_MANAGER:", is_manager)

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={"user": user, "subscriptions": subscriptions, "categories": categories, "family": family, "is_manager": is_manager }
        )
    finally:
        cursor.close()
        conn.close()


# ==================== SUBSCRIPTIONS ===================== #

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

        # Get original start date
        cursor.execute("SELECT SUB_SDate FROM SUBSCRIPTIONS WHERE SUB_ID = %s", (sub_id,))
        sub_sdate = cursor.fetchone()[0]

        # Delete all non-cancelled payments and regenerate from original start date
        cursor.execute(
            "DELETE FROM SUBSCRIPTION_PAYMENTS WHERE SUB_ID = %s AND SUBPAY_Status != 'Cancelled'",
            (sub_id,)
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


# --- DELETE SUBSCRIPTION ---
@app.post("/delete-subscription")
def delete_subscription(user_id: int = Form(...), sub_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        # Delete child records first to avoid foreign key constraint errors
        cursor.execute("DELETE FROM SUBSCRIPTION_PAYMENTS WHERE SUB_ID = %s", (sub_id,))
        cursor.execute("DELETE FROM SUBSCRIPTION_VERSIONS WHERE SUB_ID = %s", (sub_id,))
        cursor.execute("DELETE FROM SUBSCRIPTIONS WHERE SUB_ID = %s AND USER_ID = %s", (sub_id, user_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)


# --- UPDATE PAYMENT ---
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




# ==================== FAMILY ===================== #

# --- FAMILY PAGE ---
@app.get("/{user_id}/family")
def family_page(request: Request, user_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT F.* FROM FAMILIES F
            JOIN FAMILY_MANAGERS FM ON F.FAMMAN_ID = FM.FAMMAN_ID
            WHERE FM.USER_ID = %s
        """, (user_id,))
        family = cursor.fetchone()

        members = []
       
        monthly_total = 0
        member_totals = {}

        if family:
            cursor.execute("""
                SELECT U.USER_ID, U.USER_FName, U.USER_LName, U.USER_Email
                FROM FAMILY_USERS FU
                JOIN USERS U ON FU.USER_ID = U.USER_ID
                WHERE FU.FAM_ID = %s
            """, (family['FAM_ID'],))
            members = cursor.fetchall()

            cursor.execute("""
                SELECT U.USER_ID, U.USER_FName, U.USER_LName,
                    S.SUB_ID, S.SUB_Name, S.SUB_CAT,
                    SP.SUBPAY_Cost, SP.SUBPAY_Date, SP.SUBPAY_Status,
                    SV.SUBVER_FREQ
                FROM SUBSCRIPTIONS S
                JOIN USERS U ON S.USER_ID = U.USER_ID
                JOIN SUBSCRIPTION_PAYMENTS SP ON S.SUB_ID = SP.SUB_ID
                JOIN SUBSCRIPTION_VERSIONS SV ON SV.SUBVER_ID = (
                    SELECT SUBVER_ID FROM SUBSCRIPTION_VERSIONS
                    WHERE SUB_ID = S.SUB_ID
                    ORDER BY SUBVER_DateAdded DESC LIMIT 1
                )
                WHERE S.USER_ID = %s  -- manager
                OR S.USER_ID IN (
                    SELECT USER_ID FROM FAMILY_USERS WHERE FAM_ID = %s
                )
                ORDER BY U.USER_LName, SP.SUBPAY_Date
            """, (user_id, family['FAM_ID'],))
            
            _subs = cursor.fetchall()

            seen_subs = set()
            member_totals = {}
            for s in _subs:
                if s['SUB_ID'] not in seen_subs and s['SUBPAY_Status'] == 'Active':
                    seen_subs.add(s['SUB_ID'])
                    freq = s['SUBVER_FREQ']
                    cost = float(s['SUBPAY_Cost'])
                    uid = s['USER_ID']
                    if freq == 'Weekly':
                        amount = cost * 52 / 12
                    elif freq == 'Monthly':
                        amount = cost
                    elif freq == 'Quarterly':
                        amount = cost / 3
                    elif freq == 'Annually':
                        amount = cost / 12
                    else:
                        amount = 0
                    monthly_total += amount
                    member_totals[uid] = round(member_totals.get(uid, 0) + amount, 2)

                    monthly_total = round(monthly_total, 2)

        family = json.loads(json.dumps(family, default=serialize)) if family else None
        members = json.loads(json.dumps(members, default=serialize))

        cursor.execute("SELECT * FROM USERS WHERE USER_ID = %s", (user_id,))
        user = cursor.fetchone()
        user = json.loads(json.dumps(user, default=serialize))

        return templates.TemplateResponse(
            request=request,
            name="family.html",
            context={"user": user, "family": family, "members": members, "monthly_total": monthly_total, "member_totals": member_totals}
        )
    finally:
        cursor.close()
        conn.close()

# --- FAMILY: ADD MEMBER ---
@app.post("/add-user")
def add_user(fam_id: int = Form(...), user_email: str = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    manager_id = None
    try:
        cursor.execute("SELECT USER_ID FROM USERS WHERE USER_Email = %s", (user_email,))
        user = cursor.fetchone()
        if not user:
            return {"error": "No user found with that email"}

        user_id = user['USER_ID']

        cursor.execute("SELECT * FROM FAMILY_USERS WHERE USER_ID = %s", (user_id,))
        if cursor.fetchone():
            return {"error": "User is already in a family"}

        cursor.execute(
            "INSERT INTO FAMILY_USERS (FAM_ID, USER_ID) VALUES (%s, %s)",
            (fam_id, user_id)
        )
        conn.commit()

        cursor.execute("""
            SELECT FM.USER_ID FROM FAMILIES F
            JOIN FAMILY_MANAGERS FM ON F.FAMMAN_ID = FM.FAMMAN_ID
            WHERE F.FAM_ID = %s
        """, (fam_id,))
        manager = cursor.fetchone()
        manager_id = manager['USER_ID']
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{manager_id}/family", status_code=303)



# --- FAMILY: Leave Family ---
@app.post("/leave-family")
def leave_family(user_id: int = Form(...), fam_id: int = Form(...), next: str = Form(None)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM FAMILY_USERS WHERE USER_ID = %s AND FAM_ID = %s",
            (user_id, fam_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url= next or f"/{user_id}/dashboard", status_code=303)


# --- FAMILY: SET SPENDING LIMIT ---
@app.post("/assign-spend-limit")
def assign_spend_limit(fam_id: int = Form(...), manager_id: int = Form(...), fam_slimit: float = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE FAMILIES SET FAM_SLimit = %s WHERE FAM_ID = %s",
            (fam_slimit, fam_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{manager_id}/family", status_code=303)




# ==================== SYSTEM ADMIN ===================== #

# --- ADMIN PAGE ---
@app.get("/{user_id}/admin")
def admin_page(request: Request, user_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM USERS WHERE USER_ID = %s", (user_id,))
        user = cursor.fetchone()
        user = json.loads(json.dumps(user, default=serialize))

        if not is_admin(cursor, user_id):
            return templates.TemplateResponse(
                request=request,
                name="admin.html",
                context={"user": user, "is_admin": False, "families": []}
            )

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
            context={"user": user, "is_admin": True, "families": families}
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
            OR USER_Phone LIKE %s
        """, (f"%{q}%", f"%{q}%", f"%{q}%"))
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
        if not is_admin(cursor, user_id):
            return {"error": "Unauthorized"}

        cursor.execute("SELECT USER_ID FROM USERS WHERE USER_Email = %s", (manager_email,))
        user = cursor.fetchone()
        if not user:
            return {"error": "No user found with that email"}

        manager_user_id = user['USER_ID']

        cursor.execute("SELECT FAMMAN_ID FROM FAMILY_MANAGERS WHERE USER_ID = %s", (manager_user_id,))
        manager = cursor.fetchone()
        if not manager:
            cursor.execute("INSERT INTO FAMILY_MANAGERS (USER_ID) VALUES (%s)", (manager_user_id,))
            famman_id = cursor.lastrowid
        else:
            famman_id = manager['FAMMAN_ID']

        cursor.execute("SELECT FAM_ID FROM FAMILIES WHERE FAMMAN_ID = %s", (famman_id,))
        if cursor.fetchone():
            return {"error": "This user already manages a family"}

        cursor.execute(
        "INSERT INTO FAMILIES (FAM_Name, FAMMAN_ID, FAM_SLimit) VALUES (%s, %s, %s)",
        (fam_name, famman_id, fam_slimit)
        )
        fam_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO FAMILY_USERS (FAM_ID, USER_ID) VALUES (%s, %s)",
            (fam_id, manager_user_id)
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
        if not is_admin(cursor, user_id):
            return {"error": "Unauthorized"}

        cursor.execute("SELECT USER_ID FROM USERS WHERE USER_Email = %s", (manager_email,))
        user = cursor.fetchone()
        if not user:
            return {"error": "No user found with that email"}

        manager_user_id = user['USER_ID']

        # Check if this user is an admin — admins cannot be family managers
        cursor.execute("SELECT * FROM SYSTEM_ADMINS WHERE USER_ID = %s", (manager_user_id,))
        if cursor.fetchone():
            return {"error": "This user is a System Admin and cannot be a Family Manager"}

        # Get or create a FAMILY_MANAGERS record for the new manager
        cursor.execute("SELECT FAMMAN_ID FROM FAMILY_MANAGERS WHERE USER_ID = %s", (manager_user_id,))
        manager = cursor.fetchone()
        if not manager:
            cursor.execute("INSERT INTO FAMILY_MANAGERS (USER_ID) VALUES (%s)", (manager_user_id,))
            famman_id = cursor.lastrowid
        else:
            famman_id = manager['FAMMAN_ID']

        # Make sure the new manager doesn't already manage a different family
        cursor.execute("SELECT FAM_ID FROM FAMILIES WHERE FAMMAN_ID = %s AND FAM_ID != %s", (famman_id, fam_id))
        if cursor.fetchone():
            return {"error": "This user already manages another family"}

        # Reassign the family to the new manager
        cursor.execute("UPDATE FAMILIES SET FAMMAN_ID = %s WHERE FAM_ID = %s", (famman_id, fam_id))

        # Clean up orphaned FAMILY_MANAGERS records — remove any manager no longer managing a family
        cursor.execute("""
            DELETE FROM FAMILY_MANAGERS
            WHERE FAMMAN_ID NOT IN (SELECT FAMMAN_ID FROM FAMILIES)
        """)

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/admin", status_code=303)



# --- ADMIN: DISSOLVE FAMILY ---
@app.post("/admin/dissolve-family")
def dissolve_family(fam_id: int = Form(...), user_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        if not is_admin(cursor, user_id):
            return {"error": "Unauthorized"}

        cursor.execute("DELETE FROM FAMILY_USERS WHERE FAM_ID = %s", (fam_id,))
        cursor.execute("DELETE FROM FAMILIES WHERE FAM_ID = %s", (fam_id,))

        # Clean up the orphaned FAMILY_MANAGERS record
        cursor.execute("""
            DELETE FROM FAMILY_MANAGERS
            WHERE FAMMAN_ID NOT IN (SELECT FAMMAN_ID FROM FAMILIES)
        """)

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
    target_user_id: int = Form(...),
    user_fname: str = Form(...),
    user_lname: str = Form(...),
    user_email: str = Form(...),
    user_phone: str = Form(None)
):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        if not is_admin(cursor, user_id):
            return {"error": "Unauthorized"}

        cursor.execute(
            "UPDATE USERS SET USER_FName = %s, USER_LName = %s, USER_Email = %s, USER_Phone = %s WHERE USER_ID = %s",
            (user_fname, user_lname, user_email, user_phone, target_user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/admin", status_code=303)


# --- ADMIN: DELETE USER ---
@app.post("/admin/delete-user")
def admin_delete_user(user_id: int = Form(...), target_user_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        if not is_admin(cursor, user_id):
            return {"error": "Unauthorized"}

        # Dissolve family if target is a manager
        cursor.execute("SELECT FAMMAN_ID FROM FAMILY_MANAGERS WHERE USER_ID = %s", (target_user_id,))
        manager_row = cursor.fetchone()
        if manager_row:
            famman_id = manager_row["FAMMAN_ID"]
            cursor.execute("SELECT FAM_ID FROM FAMILIES WHERE FAMMAN_ID = %s", (famman_id,))
            family_row = cursor.fetchone()
            if family_row:
                fam_id = family_row["FAM_ID"]
                cursor.execute("DELETE FROM FAMILY_USERS WHERE FAM_ID = %s", (fam_id,))
                cursor.execute("DELETE FROM FAMILIES WHERE FAM_ID = %s", (fam_id,))
        cursor.execute("DELETE FROM FAMILY_MANAGERS WHERE USER_ID = %s", (target_user_id,))

        # Delete user's data in dependency order
        cursor.execute("DELETE FROM SUBSCRIPTION_PAYMENTS WHERE SUB_ID IN (SELECT SUB_ID FROM SUBSCRIPTIONS WHERE USER_ID = %s)", (target_user_id,))
        cursor.execute("DELETE FROM SUBSCRIPTION_VERSIONS WHERE SUB_ID IN (SELECT SUB_ID FROM SUBSCRIPTIONS WHERE USER_ID = %s)", (target_user_id,))
        cursor.execute("DELETE FROM SUBSCRIPTIONS WHERE USER_ID = %s", (target_user_id,))
        cursor.execute("DELETE FROM CATEGORIES WHERE USER_ID = %s", (target_user_id,))
        cursor.execute("DELETE FROM FAMILY_USERS WHERE USER_ID = %s", (target_user_id,))
        cursor.execute("DELETE FROM FAMILY_MANAGERS WHERE USER_ID = %s", (target_user_id,))
        cursor.execute("DELETE FROM SYSTEM_ADMINS WHERE USER_ID = %s", (target_user_id,))
        cursor.execute("DELETE FROM USERS WHERE USER_ID = %s", (target_user_id,))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        return {"status": "error"}
    finally:
        cursor.close()
        conn.close()



# --- ADMIN: UPDATE FAMILY ---
@app.post("/admin/update-family")
def admin_update_family(
    user_id: int = Form(...),
    fam_id: int = Form(...),
    fam_name: str = Form(...),
    fam_slimit: float = Form(None)
):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        if not is_admin(cursor, user_id):
            return {"error": "Unauthorized"}

        cursor.execute(
            "UPDATE FAMILIES SET FAM_Name = %s, FAM_SLimit = %s WHERE FAM_ID = %s",
            (fam_name, fam_slimit, fam_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/admin", status_code=303)



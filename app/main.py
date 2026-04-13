import os
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from mysql.connector import pooling
from dotenv import load_dotenv

import json
from decimal import Decimal
from datetime import date, datetime

def serialize(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

load_dotenv()

app = FastAPI(title="Velocity Ride Share API")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Connection Pool Initialization (Size 10)
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



# --- DASHBOARD route ---
@app.get("/{user_id}/dashboard")
def dashboard(request: Request, user_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        #get user info
        cursor.execute("SELECT * FROM USERS WHERE USER_ID = %s", (user_id,))
        user = cursor.fetchone()
        
        # Get the most recent version of the subscriptions for a specific USER_ID
        query = """
            SELECT S.SUB_ID, S.SUB_Name, S.SUB_Status, S.SUB_SDate, S.SUB_CancelDate,
                SV.SUBVER_Cost, SV.SUBVER_FREQ, S.SUB_CAT
            FROM SUBSCRIPTIONS S
            JOIN SUBSCRIPTION_VERSIONS SV ON S.SUB_ID = SV.SUB_ID
            WHERE S.USER_ID = %s
                AND SV.SUBVER_ID = (
                    SELECT SUBVER_ID
                    FROM SUBSCRIPTION_VERSIONS
                    WHERE SUB_ID = S.SUB_ID
                    ORDER BY SUBVER_DateAdded DESC
                    LIMIT 1
                )
            ORDER BY S.SUB_Name
        """
        cursor.execute(query, (user_id,))
        subscriptions = cursor.fetchall()

        subscriptions = json.loads(json.dumps(subscriptions, default=serialize))
        user = json.loads(json.dumps(user, default=serialize))

        return templates.TemplateResponse(
            request=request, 
            name="dashboard.html", 
            context={"user": user, "subscriptions": subscriptions }
        )
    finally:
        cursor.close()
        conn.close()

# --- REGISTER ACCOUNT---
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


# --- ADD SUBSCRIPTION ---
@app.post("/add-subscription")
def add_subscription(
    user_id: int = Form(...),
    sub_name: str = Form(...),
    sub_cat: str = Form(None),
    sub_sdate: str = Form(...),
    sub_status: str = Form(...),
    subver_cost: float = Form(...),
    subver_freq: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()

    # we need to insert a subscription AND make a version on first add
    try:
        # start transaction
        cursor.execute(  
            "INSERT INTO SUBSCRIPTIONS (USER_ID, SUB_Name, SUB_CAT, SUB_SDate, SUB_Status) VALUES (%s, %s, %s, %s, %s)",
            (user_id, sub_name, sub_cat, sub_sdate, sub_status)
        )
        sub_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO SUBSCRIPTION_VERSIONS (SUB_ID, SUBVER_Cost, SUBVER_FREQ, SUBVER_EffectiveDate) VALUES (%s, %s, %s, %s)",
            (sub_id, subver_cost, subver_freq, sub_sdate)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)
        
# --- JOIN FAMILY ---
@app.post("/join-family")
def join_family(
    user_id: int = Form(...),
    fam_id: int = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO FAMILY_USERS (FAM_ID, USER_ID) VALUES (%s, %s)",
            (fam_id, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- LEAVE FAMILY ---
@app.post("/leave-family")
def leave_family(
    user_id: int = Form(...),
    fam_id: int = Form(...)
):
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
    return RedirectResponse(url="/", status_code=303)
    
        
            
# --- UPDATE SUBSCRIPTION (name, category, date, status) ---
@app.post("/update-subscription")
def update_subscription(
    user_id: int = Form(...),
    sub_id: int = Form(...),
    sub_name: str = Form(...),
    sub_cat: str = Form(None),
    sub_sdate: str = Form(...),
    sub_status: str = Form(...),
    subver_cost: float = Form(...),
    subver_freq: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
        """UPDATE SUBSCRIPTIONS 
        SET SUB_Name = %s, SUB_CAT = %s, SUB_SDate = %s, SUB_Status = %s,
            SUB_CancelDate = CASE WHEN %s = 'Cancelled' THEN CURDATE() ELSE NULL END
        WHERE SUB_ID = %s""",
        (sub_name, sub_cat, sub_sdate, sub_status, sub_status, sub_id)
    )
        cursor.execute(
            "INSERT INTO SUBSCRIPTION_VERSIONS (SUB_ID, SUBVER_Cost, SUBVER_FREQ, SUBVER_EffectiveDate) VALUES (%s, %s, %s, %s)",
            (sub_id, subver_cost, subver_freq, sub_sdate)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)


# --- UPDATE SUBSCRIPTION COST (creates new version) ---
@app.post("/update-subscription-cost")
def update_subscription_cost(
    sub_id: int = Form(...),
    subver_cost: float = Form(...),
    subver_freq: str = Form(...),
    subver_effective_date: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO SUBSCRIPTION_VERSIONS (SUB_ID, SUBVER_Cost, SUBVER_FREQ, SUBVER_EffectiveDate) VALUES (%s, %s, %s, %s)",
            (sub_id, subver_cost, subver_freq, subver_effective_date)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- DELETE SUBSCRIPTION ---
@app.post("/delete-subscription")
def delete_subscription(sub_id: int = Form(...), user_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        # Delete dependent rows first
        cursor.execute("DELETE FROM SUBSCRIPTION_PAYMENTS WHERE SUB_ID = %s", (sub_id,))
        cursor.execute("DELETE FROM SUBSCRIPTION_VERSIONS WHERE SUB_ID = %s", (sub_id,))
        cursor.execute("DELETE FROM SUBSCRIPTIONS WHERE SUB_ID = %s", (sub_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url=f"/{user_id}/dashboard", status_code=303)


# --- REQUEST SUBSCRIPTION (sets status to Pending) ---
@app.post("/request-subscription")
def request_subscription(
    user_id: int = Form(...),
    sub_name: str = Form(...),
    cat_id: int = Form(None),
    sub_sdate: str = Form(...),
    subver_cost: float = Form(...),
    subver_freq: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        # Insert subscription with Pending status
        cursor.execute(
            "INSERT INTO SUBSCRIPTIONS (USER_ID, CAT_ID, SUB_Name, SUB_SDate, SUB_Status) VALUES (%s, %s, %s, %s, 'Pending')",
            (user_id, cat_id, sub_name, sub_sdate)
        )
        sub_id = cursor.lastrowid

        # Insert first version
        cursor.execute(
            "INSERT INTO SUBSCRIPTION_VERSIONS (SUB_ID, SUBVER_Cost, SUBVER_FREQ, SUBVER_EffectiveDate) VALUES (%s, %s, %s, %s)",
            (sub_id, subver_cost, subver_freq, sub_sdate)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- APPROVE SUBSCRIPTION ---
@app.post("/approve-subscription")
def approve_subscription(sub_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE SUBSCRIPTIONS SET SUB_Status = 'Active' WHERE SUB_ID = %s AND SUB_Status = 'Pending'",
            (sub_id,)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- DECLINE SUBSCRIPTION ---
@app.post("/decline-subscription")
def decline_subscription(sub_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE SUBSCRIPTIONS SET SUB_Status = 'Declined' WHERE SUB_ID = %s AND SUB_Status = 'Pending'",
            (sub_id,)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)



# --- CREATE FAMILY ---
@app.post("/create-family")
def create_family(
    fam_name: str = Form(...),
    famman_id: int = Form(...),
    fam_slimit: float = Form(None)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
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
    return RedirectResponse(url="/", status_code=303)


# --- INVITE USER TO FAMILY ---  (same as Join Family)
@app.post("/invite-user")
def invite_user(
    fam_id: int = Form(...),
    user_id: int = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO FAMILY_USERS (FAM_ID, USER_ID) VALUES (%s, %s)",
            (fam_id, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- REMOVE USER FROM FAMILY ---
@app.post("/remove-user")
def remove_user(
    fam_id: int = Form(...),
    user_id: int = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM FAMILY_USERS WHERE FAM_ID = %s AND USER_ID = %s",
            (fam_id, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- VIEW FAMILY SUBSCRIPTIONS ---
@app.get("/family-subscriptions/{fam_id}")
def family_subscriptions(request: Request, fam_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT U.USER_ID, U.USER_FName, U.USER_LName, S.SUB_ID, S.SUB_Name, 
                   S.SUB_Status, SV.SUBVER_Cost, SV.SUBVER_FREQ
            FROM FAMILY_USERS FU
            JOIN USERS U ON FU.USER_ID = U.USER_ID
            JOIN SUBSCRIPTIONS S ON U.USER_ID = S.USER_ID
            JOIN SUBSCRIPTION_VERSIONS SV ON S.SUB_ID = SV.SUB_ID
            WHERE FU.FAM_ID = %s
            AND SV.SUBVER_EffectiveDate = (
                SELECT MAX(SUBVER_EffectiveDate)
                FROM SUBSCRIPTION_VERSIONS
                WHERE SUB_ID = S.SUB_ID
            )
        """
        cursor.execute(query, (fam_id,))
        family_subs = cursor.fetchall()

        return templates.TemplateResponse(
            request=request,
            name="family.html",
            context={"family_subs": family_subs}
        )
    finally:
        cursor.close()
        conn.close()


# --- ASSIGN FAMILY SPENDING LIMIT ---
@app.post("/assign-spend-limit")
def assign_spend_limit(
    fam_id: int = Form(...),
    fam_slimit: float = Form(...)
):
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
    return RedirectResponse(url="/", status_code=303)


# --- VIEW FAMILY SUBSCRIPTION HISTORY ---
@app.get("/family-history/{fam_id}")
def family_history(request: Request, fam_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT U.USER_FName, U.USER_LName, S.SUB_Name, 
                   SP.SUBPAY_Cost, SP.SUBPAY_Date
            FROM FAMILY_USERS FU
            JOIN USERS U ON FU.USER_ID = U.USER_ID
            JOIN SUBSCRIPTIONS S ON U.USER_ID = S.USER_ID
            JOIN SUBSCRIPTION_PAYMENTS SP ON S.SUB_ID = SP.SUB_ID
            WHERE FU.FAM_ID = %s
            ORDER BY SP.SUBPAY_Date DESC
        """
        cursor.execute(query, (fam_id,))
        history = cursor.fetchall()

        return templates.TemplateResponse(
            request=request,
            name="family_history.html",
            context={"history": history}
        )
    finally:
        cursor.close()
        conn.close()
    

# --- ADMIN CONTROLS --- 
# --- LOOKUP USER + THEIR SUBSCRIPTIONS ---
@app.get("/admin/user/{user_id}")
def admin_get_user(request: Request, user_id: int):
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        # Get user profile
        cursor.execute("SELECT * FROM USERS WHERE USER_ID = %s", (user_id,))
        user = cursor.fetchone()

        # Get all their subscriptions with latest version
        query = """
            SELECT S.SUB_ID, S.SUB_Name, S.SUB_Status, S.SUB_SDate,
                   SV.SUBVER_Cost, SV.SUBVER_FREQ, C.CAT_Name
            FROM SUBSCRIPTIONS S
            JOIN SUBSCRIPTION_VERSIONS SV ON S.SUB_ID = SV.SUB_ID
            LEFT JOIN CATEGORIES C ON S.CAT_ID = C.CAT_ID
            WHERE S.USER_ID = %s
            AND SV.SUBVER_EffectiveDate = (
                SELECT MAX(SUBVER_EffectiveDate)
                FROM SUBSCRIPTION_VERSIONS
                WHERE SUB_ID = S.SUB_ID
            )
        """
        cursor.execute(query, (user_id,))
        subscriptions = cursor.fetchall()

        return templates.TemplateResponse(
            request=request,
            name="admin_user.html",
            context={"user": user, "subscriptions": subscriptions}
        )
    finally:
        cursor.close()
        conn.close()


# --- ADMIN UPDATE ANY SUBSCRIPTION ---
@app.post("/admin/update-subscription")
def admin_update_subscription(
    sub_id: int = Form(...),
    sub_name: str = Form(...),
    cat_id: int = Form(None),
    sub_sdate: str = Form(...),
    sub_status: str = Form(...),
    subver_cost: float = Form(...),
    subver_freq: str = Form(...),
    subver_effective_date: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        # Update subscription details
        cursor.execute(
            "UPDATE SUBSCRIPTIONS SET SUB_Name = %s, CAT_ID = %s, SUB_SDate = %s, SUB_Status = %s WHERE SUB_ID = %s",
            (sub_name, cat_id, sub_sdate, sub_status, sub_id)
        )
        # Add new version for cost/freq change
        cursor.execute(
            "INSERT INTO SUBSCRIPTION_VERSIONS (SUB_ID, SUBVER_Cost, SUBVER_FREQ, SUBVER_EffectiveDate) VALUES (%s, %s, %s, %s)",
            (sub_id, subver_cost, subver_freq, subver_effective_date)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- ADMIN ADD SUBSCRIPTION FOR ANY USER ---
@app.post("/admin/add-subscription")
def admin_add_subscription(
    user_id: int = Form(...),
    sub_name: str = Form(...),
    cat_id: int = Form(None),
    sub_sdate: str = Form(...),
    sub_status: str = Form(...),
    subver_cost: float = Form(...),
    subver_freq: str = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO SUBSCRIPTIONS (USER_ID, CAT_ID, SUB_Name, SUB_SDate, SUB_Status) VALUES (%s, %s, %s, %s, %s)",
            (user_id, cat_id, sub_name, sub_sdate, sub_status)
        )
        sub_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO SUBSCRIPTION_VERSIONS (SUB_ID, SUBVER_Cost, SUBVER_FREQ, SUBVER_EffectiveDate) VALUES (%s, %s, %s, %s)",
            (sub_id, subver_cost, subver_freq, sub_sdate)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- ADMIN DELETE ANY SUBSCRIPTION ---
@app.post("/admin/delete-subscription")
def admin_delete_subscription(sub_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM SUBSCRIPTION_PAYMENTS WHERE SUB_ID = %s", (sub_id,))
        cursor.execute("DELETE FROM SUBSCRIPTION_VERSIONS WHERE SUB_ID = %s", (sub_id,))
        cursor.execute("DELETE FROM SUBSCRIPTIONS WHERE SUB_ID = %s", (sub_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- ADMIN EDIT ANY ACCOUNT ---
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
    return RedirectResponse(url="/", status_code=303)


# --- ADMIN DELETE ANY ACCOUNT ---
@app.post("/admin/delete-user")
def admin_delete_user(user_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM SUBSCRIPTION_PAYMENTS WHERE SUB_ID IN (SELECT SUB_ID FROM SUBSCRIPTIONS WHERE USER_ID = %s)", (user_id,))
        cursor.execute("DELETE FROM SUBSCRIPTION_VERSIONS WHERE SUB_ID IN (SELECT SUB_ID FROM SUBSCRIPTIONS WHERE USER_ID = %s)", (user_id,))
        cursor.execute("DELETE FROM SUBSCRIPTIONS WHERE USER_ID = %s", (user_id,))
        cursor.execute("DELETE FROM FAMILY_USERS WHERE USER_ID = %s", (user_id,))
        cursor.execute("DELETE FROM CATEGORIES WHERE USER_ID = %s", (user_id,))
        cursor.execute("DELETE FROM USERS WHERE USER_ID = %s", (user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- ADMIN CREATE FAMILY ---
@app.post("/admin/create-family")
def admin_create_family(
    fam_name: str = Form(...),
    famman_id: int = Form(...),
    fam_slimit: float = Form(None)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
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
    return RedirectResponse(url="/", status_code=303)


# --- ADMIN REASSIGN FAMILY MANAGER ---
@app.post("/admin/reassign-family-manager")
def reassign_family_manager(
    fam_id: int = Form(...),
    famman_id: int = Form(...)
):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE FAMILIES SET FAMMAN_ID = %s WHERE FAM_ID = %s",
            (famman_id, fam_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


# --- ADMIN DISSOLVE FAMILY ---
@app.post("/admin/dissolve-family")
def dissolve_family(fam_id: int = Form(...)):
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM FAMILY_USERS WHERE FAM_ID = %s", (fam_id,))
        cursor.execute("DELETE FROM FAMILIES WHERE FAM_ID = %s", (fam_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    return RedirectResponse(url="/", status_code=303)


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






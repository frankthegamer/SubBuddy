"""
Database Initialization Module
Responsible for Schema creation and idempotent data seeding.
Uses Environment Variables via python-dotenv for security.
"""
import mysql.connector
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())



def init_db():
    """Establishes initial connection to create DB and Tables."""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS")
        )
        cursor = conn.cursor()
        
        # Create Database
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('DB_NAME')}")
        cursor.execute(f"USE {os.getenv('DB_NAME')}")

        # DDL Statements
        tables = {
            "USERS": "CREATE TABLE IF NOT EXISTS USERS (USER_ID INT PRIMARY KEY AUTO_INCREMENT, USER_FName VARCHAR(50) NOT NULL, USER_LName VARCHAR(50) NOT NULL, USER_Email VARCHAR(100) NOT NULL UNIQUE, USER_Password VARCHAR(255) NOT NULL, USER_Phone VARCHAR(20))",
            "CATEGORIES": "CREATE TABLE IF NOT EXISTS CATEGORIES (CAT_ID INT PRIMARY KEY AUTO_INCREMENT, CAT_Name VARCHAR(50) NOT NULL, USER_ID INT, FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID))",         
            "FAMILY_MANAGERS":"CREATE TABLE IF NOT EXISTS FAMILY_MANAGERS (FAMMAN_ID INT PRIMARY KEY AUTO_INCREMENT, USER_ID INT NOT NULL, FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID))",
            "SYSTEM_ADMINS": "CREATE TABLE IF NOT EXISTS SYSTEM_ADMINS (ADMIN_ID INT PRIMARY KEY AUTO_INCREMENT, USER_ID INT NOT NULL, FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID))",
            "FAMILIES": "CREATE TABLE IF NOT EXISTS FAMILIES (FAM_ID INT PRIMARY KEY AUTO_INCREMENT, FAM_Name VARCHAR(100) NOT NULL, FAM_SLimit DECIMAL(10,2), FAMMAN_ID INT NOT NULL, FOREIGN KEY (FAMMAN_ID) REFERENCES FAMILY_MANAGERS(FAMMAN_ID))",
            "FAMILY_USERS": "CREATE TABLE IF NOT EXISTS FAMILY_USERS (FAM_ID INT NOT NULL, USER_ID INT NOT NULL, PRIMARY KEY (FAM_ID, USER_ID), FOREIGN KEY (FAM_ID) REFERENCES FAMILIES(FAM_ID), FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID))",
            "SUBSCRIPTIONS": "CREATE TABLE IF NOT EXISTS SUBSCRIPTIONS (SUB_ID INT PRIMARY KEY AUTO_INCREMENT, USER_ID INT NOT NULL, SUB_CAT VARCHAR(100), SUB_Name VARCHAR(100) NOT NULL, SUB_SDate DATE NOT NULL, FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID))",
            "SUBSCRIPTION_VERSIONS": "CREATE TABLE IF NOT EXISTS SUBSCRIPTION_VERSIONS (SUBVER_ID INT PRIMARY KEY AUTO_INCREMENT, SUB_ID INT NOT NULL, SUBVER_Cost DECIMAL(10,2) NOT NULL, SUBVER_FREQ VARCHAR(20) NOT NULL, SUBVER_EffectiveDate DATE NOT NULL, SUBVER_DateAdded DATETIME DEFAULT NOW(), FOREIGN KEY (SUB_ID) REFERENCES SUBSCRIPTIONS(SUB_ID))",
            "SUBSCRIPTION_PAYMENTS": "CREATE TABLE IF NOT EXISTS SUBSCRIPTION_PAYMENTS (SUBPAY_ID INT PRIMARY KEY AUTO_INCREMENT, SUB_ID INT NOT NULL, SUBPAY_Cost DECIMAL(10,2) NOT NULL, SUBPAY_Date DATE NOT NULL, SUBPAY_Status VARCHAR(20) DEFAULT 'Active', FOREIGN KEY (SUB_ID) REFERENCES SUBSCRIPTIONS(SUB_ID))",
        }

        for name, ddl in tables.items():
            cursor.execute(ddl)
            print(f"Table '{name}' verified.")


        # Triggers — these enforce disjoint specialization (a user can only be an admin OR a family manager, not both)
        cursor.execute("DROP TRIGGER IF EXISTS before_insert_admin")
        cursor.execute("""
            CREATE TRIGGER before_insert_admin
            BEFORE INSERT ON SYSTEM_ADMINS
            FOR EACH ROW
            BEGIN
                IF EXISTS (SELECT * FROM FAMILY_MANAGERS WHERE USER_ID = NEW.USER_ID) THEN
                    SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'User is already a Family Manager';
                END IF;
            END
        """)
        print("Trigger 'before_insert_admin' verified.")

        cursor.execute("DROP TRIGGER IF EXISTS before_insert_family_manager")
        cursor.execute("""
            CREATE TRIGGER before_insert_family_manager
            BEFORE INSERT ON FAMILY_MANAGERS
            FOR EACH ROW
            BEGIN
                IF EXISTS (SELECT * FROM SYSTEM_ADMINS WHERE USER_ID = NEW.USER_ID) THEN
                    SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'User is already a System Admin';
                END IF;
            END
        """)
        print("Trigger 'before_insert_family_manager' verified.")


        # Seed initial system admin user
        cursor.execute("SELECT USER_ID FROM USERS WHERE USER_Email = 'admin@subbuddy.com'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO USERS (USER_FName, USER_LName, USER_Email, USER_Password)
                VALUES ('Admin', 'User', 'admin@subbuddy.com', 'admin123')
            """)
            admin_id = cursor.lastrowid
            cursor.execute("INSERT INTO SYSTEM_ADMINS (USER_ID) VALUES (%s)", (admin_id,))
            print("Admin user seeded.")
        else:
            print("Admin user already exists, skipping.")

        conn.commit()
        print("--- Database Setup Complete ---")
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == '__main__':
    init_db()
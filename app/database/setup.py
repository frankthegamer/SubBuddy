"""
Database Initialization Module
Responsible for Schema creation and idempotent data seeding.
Uses Environment Variables via python-dotenv for security.
"""
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

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
            "SUBSCRIPTIONS": "CREATE TABLE IF NOT EXISTS SUBSCRIPTIONS (SUB_ID INT PRIMARY KEY AUTO_INCREMENT, USER_ID INT NOT NULL, SUB_CAT VARCHAR(50), SUB_Name VARCHAR(100) NOT NULL, SUB_SDate DATE NOT NULL, SUB_Status VARCHAR(20) NOT NULL, SUB_CancelDate DATE, FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID))",
            "SUBSCRIPTION_VERSIONS": "CREATE TABLE IF NOT EXISTS SUBSCRIPTION_VERSIONS (SUBVER_ID INT PRIMARY KEY AUTO_INCREMENT, SUB_ID INT NOT NULL, SUBVER_Cost DECIMAL(10,2) NOT NULL, SUBVER_FREQ VARCHAR(20) NOT NULL, SUBVER_EffectiveDate DATE NOT NULL, SUBVER_DateAdded DATETIME DEFAULT NOW(), FOREIGN KEY (SUB_ID) REFERENCES SUBSCRIPTIONS(SUB_ID))",
            "SUBSCRIPTION_PAYMENTS": "CREATE TABLE IF NOT EXISTS SUBSCRIPTION_PAYMENTS (SUBPAY_ID INT PRIMARY KEY AUTO_INCREMENT, SUB_ID INT NOT NULL, SUBPAY_Cost DECIMAL(10,2) NOT NULL, SUBPAY_Date DATE NOT NULL, FOREIGN KEY (SUB_ID) REFERENCES SUBSCRIPTIONS(SUB_ID))"
        }

        for name, ddl in tables.items():
            cursor.execute(ddl)
            print(f"Table '{name}' verified.")

        
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

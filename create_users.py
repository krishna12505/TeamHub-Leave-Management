from database import get_connection
from werkzeug.security import generate_password_hash
from getpass import getpass
import mysql.connector


def create_user(full_name, email, password, role):

    connection = get_connection()

    if connection is None:
        print("Database connection failed!")
        return

    cursor = connection.cursor()

    try:
        # Hash the password
        hashed_password = generate_password_hash(password)

        # Insert employee or manager
        query = """
            INSERT INTO employees
            (full_name, email, password, role)
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (full_name, email, hashed_password, role)
        )

        # Get newly generated employee ID
        employee_id = cursor.lastrowid

        # Create leave balance
        balance_query = """
            INSERT INTO leave_balance
            (employee_id, total_leaves, used_leaves, remaining_leaves)
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            balance_query,
            (employee_id, 20, 0, 20)
        )

        connection.commit()

        print(f"{role.capitalize()} account created successfully!")
        print("Employee ID:", employee_id)

    except mysql.connector.IntegrityError:
        connection.rollback()
        print("This email already exists!")

    except Exception as e:
        connection.rollback()
        print("Error:", e)

    finally:
        cursor.close()
        connection.close()


# Create Manager
print("\n--- CREATE MANAGER ACCOUNT ---")

manager_name = input("Enter manager name: ")
manager_email = input("Enter manager email: ")
manager_password = getpass("Enter manager password: ")

create_user(
    manager_name,
    manager_email,
    manager_password,
    "manager"
)


# Create Employee
print("\n--- CREATE EMPLOYEE ACCOUNT ---")

employee_name = input("Enter employee name: ")
employee_email = input("Enter employee email: ")
employee_password = getpass("Enter employee password: ")

create_user(
    employee_name,
    employee_email,
    employee_password,
    "employee"
)
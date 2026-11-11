
import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta

import certifi

# CUSTOM LEAVE BALANCE ERROR


class InsufficientLeaveBalanceError(Exception):
    """Raised when an employee does not have enough available leaves."""
    pass



# HELPER: CALCULATE LEAVE DAYS
# EXCLUDES SATURDAY AND SUNDAY


def calculate_leave_days(start_date, end_date):

    if isinstance(start_date, datetime):
        start_date = start_date.date()

    if isinstance(end_date, datetime):
        end_date = end_date.date()

    if isinstance(start_date, str):
        start_date = datetime.strptime(
            start_date, "%Y-%m-%d"
        ).date()

    if isinstance(end_date, str):
        end_date = datetime.strptime(
            end_date, "%Y-%m-%d"
        ).date()

    if end_date < start_date:
        raise ValueError("End date cannot be before start date.")

    leave_days = 0
    current_date = start_date

    while current_date <= end_date:

        # Monday to Friday only
        if current_date.weekday() < 5:
            leave_days += 1

        current_date += timedelta(days=1)

    return leave_days



# HELPER: GET PENDING LEAVE DAYS
# WEEKENDS ARE NOT COUNTED


def get_pending_leave_days(
    cursor,
    employee_id,
    exclude_leave_id=None
):

    query = """
        SELECT start_date, end_date
        FROM leave_requests
        WHERE employee_id = %s
        AND status = 'Pending'
    """

    values = [employee_id]

    if exclude_leave_id is not None:
        query += " AND leave_id != %s"
        values.append(exclude_leave_id)

    cursor.execute(query, tuple(values))

    pending_requests = cursor.fetchall()

    total_pending_days = 0

    for leave in pending_requests:

        total_pending_days += calculate_leave_days(
            leave["start_date"],
            leave["end_date"]
        )

    return total_pending_days



# 1. MYSQL DATABASE CONNECTION




def get_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"),
            port=int(os.getenv("MYSQL_PORT", "4000")),
            ssl_ca=certifi.where(),
            ssl_verify_cert=True,
            connection_timeout=15
        )

        return connection

    except Error as e:
        print("Database Connection Error:", e)
        return None



# 2. CREATE EMPLOYEE

def create_employee(full_name, email, password_hash, role):

    connection = get_connection()

    if connection is None:
        return None

    cursor = connection.cursor()

    try:

        query = """
            INSERT INTO employees
            (full_name, email, password, role)
            VALUES (%s, %s, %s, %s)
        """

        values = (full_name, email, password_hash, role)

        cursor.execute(query, values)

        employee_id = cursor.lastrowid

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

        return employee_id

    except Error as e:

        connection.rollback()

        print("Employee Creation Error:", e)

        raise

    finally:

        cursor.close()
        connection.close()



# 3. GET EMPLOYEE BY EMAIL


def get_employee_by_email(email):

    connection = get_connection()

    if connection is None:
        return None

    cursor = connection.cursor(dictionary=True)

    try:

        query = """
            SELECT employee_id, full_name, email, password, role
            FROM employees
            WHERE email = %s
        """

        cursor.execute(query, (email,))

        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()


# 4. GET EMPLOYEE BY ID


def get_employee_by_id(employee_id):

    connection = get_connection()

    if connection is None:
        return None

    cursor = connection.cursor(dictionary=True)

    try:

        query = """
            SELECT employee_id, full_name, email, role
            FROM employees
            WHERE employee_id = %s
        """

        cursor.execute(query, (employee_id,))

        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()



# 5. CREATE LEAVE BALANCE


def create_leave_balance(employee_id):

    connection = get_connection()

    if connection is None:
        return None

    cursor = connection.cursor()

    try:

        query = """
            INSERT INTO leave_balance
            (employee_id, total_leaves, used_leaves, remaining_leaves)
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (employee_id, 20, 0, 20)
        )

        connection.commit()

        return True

    except Error as e:

        connection.rollback()

        print("Leave Balance Error:", e)

        raise

    finally:

        cursor.close()
        connection.close()



# 6. GET LEAVE BALANCE


def get_leave_balance(employee_id):

    connection = get_connection()

    if connection is None:
        return None

    cursor = connection.cursor(dictionary=True)

    try:

        query = """
            SELECT
                total_leaves,
                used_leaves,
                remaining_leaves
            FROM leave_balance
            WHERE employee_id = %s
        """

        cursor.execute(query, (employee_id,))

        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()



# 7. GET EMPLOYEE LEAVE REQUESTS


def get_leave_requests(employee_id):

    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:

        query = """
            SELECT
                leave_id,
                leave_type,
                start_date,
                end_date,
                reason,
                status,
                applied_at
            FROM leave_requests
            WHERE employee_id = %s
            ORDER BY applied_at DESC
        """

        cursor.execute(query, (employee_id,))

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()



# 8. CREATE LEAVE REQUEST


def create_leave_request(
    employee_id,
    leave_type,
    start_date,
    end_date,
    reason
):

    connection = get_connection()

    if connection is None:
        raise Exception("Database connection failed!")

    cursor = connection.cursor(dictionary=True)

    try:

        connection.start_transaction()

        # Calculate weekdays only.

        requested_days = calculate_leave_days(
            start_date,
            end_date
        )

        # Reject weekend-only requests.

        if requested_days == 0:
            raise ValueError(
                "Your selected dates contain only weekends. "
                "Please select at least one weekday."
            )

        # Lock employee balance.

        cursor.execute(
            """
            SELECT remaining_leaves
            FROM leave_balance
            WHERE employee_id = %s
            FOR UPDATE
            """,
            (employee_id,)
        )

        balance = cursor.fetchone()

        if balance is None:
            raise Exception("Leave balance not found!")

        remaining_leaves = int(
            balance["remaining_leaves"]
        )

        # Calculate existing pending weekdays.

        pending_days = get_pending_leave_days(
            cursor,
            employee_id
        )

        available_days = max(
            0,
            remaining_leaves - pending_days
        )

        # Validate available balance.

        if requested_days > available_days:

            raise InsufficientLeaveBalanceError(
                f"Insufficient leave balance! "
                f"You requested {requested_days} day(s), "
                f"but only {available_days} day(s) "
                f"are available after accounting for "
                f"pending requests."
            )

        # Insert leave request.

        query = """
            INSERT INTO leave_requests
            (
                employee_id,
                leave_type,
                start_date,
                end_date,
                reason,
                status,
                applied_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """

        values = (
            employee_id,
            leave_type,
            start_date,
            end_date,
            reason,
            "Pending"
        )

        cursor.execute(query, values)

        leave_id = cursor.lastrowid

        connection.commit()

        return leave_id

    except Exception:

        connection.rollback()

        raise

    finally:

        cursor.close()
        connection.close()



# 9. GET ALL LEAVE REQUESTS (MANAGER)

def get_all_leave_requests():

    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:

        query = """
            SELECT
                lr.leave_id,
                lr.employee_id,
                e.full_name,
                e.email,
                lr.leave_type,
                lr.start_date,
                lr.end_date,
                lr.reason,
                lr.status,
                lr.applied_at
            FROM leave_requests lr
            JOIN employees e
                ON lr.employee_id = e.employee_id
            ORDER BY lr.applied_at DESC
        """

        cursor.execute(query)

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


# 10. APPROVE OR REJECT LEAVE REQUEST


def update_leave_status(leave_id, new_status):

    if new_status not in ["Approved", "Rejected"]:
        raise ValueError("Invalid leave status!")

    connection = get_connection()

    if connection is None:
        raise Exception("Database connection failed!")

    cursor = connection.cursor(dictionary=True)

    try:

        connection.start_transaction()

        # Lock leave request.

        cursor.execute(
            """
            SELECT
                employee_id,
                start_date,
                end_date,
                status
            FROM leave_requests
            WHERE leave_id = %s
            FOR UPDATE
            """,
            (leave_id,)
        )

        leave = cursor.fetchone()

        if leave is None:
            raise Exception("Leave request not found!")

        if leave["status"] != "Pending":

            raise Exception(
                "This request has already been processed!"
            )

        employee_id = leave["employee_id"]

        # Calculate weekdays only.

        leave_days = calculate_leave_days(
            leave["start_date"],
            leave["end_date"]
        )

        if new_status == "Approved":

            # Lock employee balance.

            cursor.execute(
                """
                SELECT remaining_leaves
                FROM leave_balance
                WHERE employee_id = %s
                FOR UPDATE
                """,
                (employee_id,)
            )

            balance = cursor.fetchone()

            if balance is None:
                raise Exception("Leave balance not found!")

            remaining_leaves = int(
                balance["remaining_leaves"]
            )

            # Count other pending requests.

            other_pending_days = get_pending_leave_days(
                cursor,
                employee_id,
                exclude_leave_id=leave_id
            )

            available_days = max(
                0,
                remaining_leaves - other_pending_days
            )

            # Final balance validation.

            if leave_days > available_days:

                raise InsufficientLeaveBalanceError(
                    f"Cannot approve this request! "
                    f"The employee has only {available_days} "
                    f"available day(s) after accounting for "
                    f"other pending requests, but this "
                    f"request requires {leave_days} day(s)."
                )

            # Deduct balance after approval validation.

            cursor.execute(
                """
                UPDATE leave_balance
                SET
                    used_leaves = used_leaves + %s,
                    remaining_leaves = remaining_leaves - %s
                WHERE employee_id = %s
                """,
                (
                    leave_days,
                    leave_days,
                    employee_id
                )
            )

        # Update request status.

        cursor.execute(
            """
            UPDATE leave_requests
            SET status = %s
            WHERE leave_id = %s
            """,
            (new_status, leave_id)
        )

        connection.commit()

        return True

    except Exception:

        connection.rollback()

        raise

    finally:

        cursor.close()
        connection.close()

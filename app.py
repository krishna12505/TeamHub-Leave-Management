
import os
import logging
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from dotenv import load_dotenv
from werkzeug.security import check_password_hash

# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()

# ==========================================
# DATABASE IMPORTS
# ==========================================

from database import (
    get_employee_by_email,
    create_leave_request,
    get_leave_balance,
    get_leave_requests,
    get_all_leave_requests,
    update_leave_status,
    calculate_leave_days,
    InsufficientLeaveBalanceError
)

# ==========================================
# APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError(
        "SECRET_KEY environment variable is not configured."
    )

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

if os.getenv("RENDER"):
    app.config["SESSION_COOKIE_SECURE"] = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# LOGIN REQUIRED DECORATOR
# ==========================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "employee_id" not in session:
            flash("Please login first.", "error")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# ==========================================
# ROLE REQUIRED DECORATOR
# ==========================================

def role_required(role):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if session.get("role") != role:

                flash(
                    "You are not authorized to access this page.",
                    "error"
                )

                return redirect(url_for("index"))

            return function(*args, **kwargs)

        return wrapper

    return decorator


# ==========================================
# HOME ROUTE
# ==========================================

@app.route("/")
def index():

    if "employee_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") == "manager":
        return redirect(url_for("manager_dashboard"))

    if session.get("role") == "employee":
        return redirect(url_for("employee_dashboard"))

    session.clear()

    return redirect(url_for("login"))


# ==========================================
# LOGIN ROUTE
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "employee_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:

            flash(
                "Please enter your email and password.",
                "error"
            )

            return render_template("login.html")

        try:

            employee = get_employee_by_email(email)

            if (
                employee
                and check_password_hash(
                    employee["password"],
                    password
                )
            ):

                session.clear()

                session["employee_id"] = employee["employee_id"]
                session["name"] = employee["full_name"]
                session["email"] = employee["email"]
                session["role"] = employee["role"]

                flash("Login successful!", "success")

                return redirect(url_for("index"))

            flash("Invalid email or password!", "error")

        except Exception:

            logger.exception("Login error")

            flash(
                "Unable to login right now. Please try again.",
                "error"
            )

    return render_template("login.html")


# ==========================================
# EMPLOYEE DASHBOARD
# ==========================================

@app.route("/employee/dashboard")
@login_required
@role_required("employee")
def employee_dashboard():

    employee_id = session["employee_id"]

    try:

        balance = get_leave_balance(employee_id)

        leave_requests = get_leave_requests(employee_id)

        for leave in leave_requests:

            if leave["start_date"] and leave["end_date"]:

                leave["working_days"] = calculate_leave_days(
                    leave["start_date"],
                    leave["end_date"]
                )

            else:

                leave["working_days"] = 0

        return render_template(
            "employee_dashboard.html",
            name=session["name"],
            balance=balance,
            leave_requests=leave_requests
        )

    except Exception:

        logger.exception("Employee dashboard error")

        flash(
            "Unable to load your dashboard.",
            "error"
        )

        return redirect(url_for("login"))


# ==========================================
# APPLY FOR LEAVE
# ==========================================

@app.route("/employee/apply-leave", methods=["GET", "POST"])
@login_required
@role_required("employee")
def apply_leave():

    if request.method == "POST":

        leave_type = request.form.get(
            "leave_type", ""
        ).strip()

        start_date = request.form.get(
            "start_date", ""
        ).strip()

        end_date = request.form.get(
            "end_date", ""
        ).strip()

        reason = request.form.get(
            "reason", ""
        ).strip()

        employee_id = session["employee_id"]

        # CHECK EMPTY FIELDS

        if not all([
            leave_type,
            start_date,
            end_date,
            reason
        ]):

            flash(
                "Please fill in all fields.",
                "error"
            )

            return redirect(url_for("apply_leave"))

        # VALIDATE LEAVE TYPE

        allowed_leave_types = [
            "Casual",
            "Sick",
            "Earned",
            "Personal"
        ]

        if leave_type not in allowed_leave_types:

            flash(
                "Please select a valid leave type.",
                "error"
            )

            return redirect(url_for("apply_leave"))

        # VALIDATE DATE FORMAT

        try:

            start = datetime.strptime(
                start_date,
                "%Y-%m-%d"
            ).date()

            end = datetime.strptime(
                end_date,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            flash(
                "Please enter valid leave dates.",
                "error"
            )

            return redirect(url_for("apply_leave"))

        # VALIDATE DATE RANGE

        if end < start:

            flash(
                "End date cannot be before start date.",
                "error"
            )

            return redirect(url_for("apply_leave"))

        # VALIDATE REASON

        if len(reason) > 1000:

            flash(
                "Reason cannot exceed 1000 characters.",
                "error"
            )

            return redirect(url_for("apply_leave"))

        try:

            # CHECK EMPLOYEE BALANCE EXISTS

            balance = get_leave_balance(employee_id)

            if not balance:

                flash(
                    "Your leave balance is not available. "
                    "Please contact your manager.",
                    "error"
                )

                return redirect(url_for("apply_leave"))

            # CALCULATE WEEKDAY-ONLY LEAVE DAYS

            requested_days = calculate_leave_days(
                start,
                end
            )

            if requested_days == 0:

                flash(
                    "Your selected dates contain only weekends. "
                    "Please select at least one weekday.",
                    "error"
                )

                return redirect(url_for("apply_leave"))

            # CREATE LEAVE REQUEST

            leave_id = create_leave_request(
                employee_id=employee_id,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                reason=reason
            )

            flash(
                f"Leave request #{leave_id} "
                f"submitted successfully! "
                f"Duration: {requested_days} working day(s).",
                "success"
            )

            return redirect(
                url_for("employee_dashboard")
            )

        except InsufficientLeaveBalanceError as e:

            flash(str(e), "error")

            return redirect(
                url_for("apply_leave")
            )

        except ValueError as e:

            flash(str(e), "error")

            return redirect(
                url_for("apply_leave")
            )

        except Exception:

            logger.exception("Leave application error")

            flash(
                "Unable to submit your leave request. "
                "Please try again.",
                "error"
            )

    return render_template("apply_leave.html")


# ==========================================
# MANAGER DASHBOARD
# ==========================================

@app.route("/manager/dashboard")
@login_required
@role_required("manager")
def manager_dashboard():

    try:

        leave_requests = get_all_leave_requests()

        for leave in leave_requests:

            if leave["start_date"] and leave["end_date"]:

                leave["working_days"] = calculate_leave_days(
                    leave["start_date"],
                    leave["end_date"]
                )

            else:

                leave["working_days"] = 0

        return render_template(
            "manager_dashboard.html",
            name=session["name"],
            leave_requests=leave_requests
        )

    except Exception:

        logger.exception("Manager dashboard error")

        flash(
            "Unable to load manager dashboard.",
            "error"
        )

        return redirect(url_for("login"))


# ==========================================
# APPROVE / REJECT LEAVE REQUEST
# ==========================================

@app.route(
    "/manager/leave/<int:leave_id>/<action>",
    methods=["POST"]
)
@login_required
@role_required("manager")
def manage_leave(leave_id, action):

    if action == "approve":

        new_status = "Approved"

    elif action == "reject":

        new_status = "Rejected"

    else:

        flash(
            "Invalid leave action.",
            "error"
        )

        return redirect(
            url_for("manager_dashboard")
        )

    try:

        update_leave_status(
            leave_id,
            new_status
        )

        flash(
            f"Leave request {new_status.lower()} successfully.",
            "success"
        )

    except InsufficientLeaveBalanceError as e:

        flash(
            str(e),
            "error"
        )

    except Exception:

        logger.exception(
            "Unable to update leave request ID %s",
            leave_id
        )

        flash(
            "Unable to update this leave request. "
            "Please try again.",
            "error"
        )

    return redirect(
        url_for("manager_dashboard")
    )


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
@login_required
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("login"))


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )

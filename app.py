from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

app = Flask(__name__)

app.config["SECRET_KEY"] = "jimtask_secret_key_2026"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = "static/uploads/screenshots"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    referral_code = db.Column(db.String(30), unique=True)
    referred_by = db.Column(db.String(30))

    task_wallet = db.Column(db.Float, default=0)
    referral_wallet = db.Column(db.Float, default=0)

    total_referrals = db.Column(db.Integer, default=0)
    referral_reward_paid = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(500), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    workers_needed = db.Column(db.Integer, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"))

    social_name = db.Column(db.String(150), nullable=False)
    screenshot = db.Column(db.String(255), nullable=False)

    status = db.Column(db.String(20), default="Pending")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Withdrawal(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    wallet = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    bank = db.Column(db.String(50), nullable=False)
    account_name = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(20), nullable=False)

    status = db.Column(db.String(20), default="Pending")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def generate_referral_code():
    return str(uuid.uuid4())[:8].upper()


def save_screenshot(file):
    if file and file.filename:
        filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{filename}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        return filename
    return None


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        referral = request.form.get("referral_code", "").strip().upper()

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
            return redirect(url_for("register"))

        my_referral_code = generate_referral_code()

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            referral_code=my_referral_code,
            referred_by=referral
        )

        db.session.add(user)

        if referral:
            referrer = User.query.filter_by(referral_code=referral).first()
            if referrer:
                referrer.total_referrals += 1
                referrer.referral_wallet += 50

        db.session.commit()

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():

    referral_link = request.host_url + "register?ref=" + current_user.referral_code

    return render_template(
        "dashboard.html",
        user=current_user,
        task_wallet=current_user.task_wallet,
        referral_wallet=current_user.referral_wallet,
        total_referrals=current_user.total_referrals,
        referral_link=referral_link
    )
@app.route("/tasks")
@login_required
def tasks():

    submitted_task_ids = [
        s.task_id for s in Submission.query.filter_by(user_id=current_user.id).all()
    ]

    all_tasks = Task.query.filter(
        ~Task.id.in_(submitted_task_ids)
    ).order_by(Task.created_at.desc()).all()

    return render_template(
        "tasks.html",
        tasks=all_tasks
    )


@app.route("/submit_task/<int:task_id>", methods=["GET", "POST"])
@login_required
def submit_task(task_id):

    task = Task.query.get_or_404(task_id)

    if request.method == "POST":

        social_name = request.form["social_name"]
        screenshot = request.files["screenshot"]

        filename = save_screenshot(screenshot)

        submission = Submission(
            user_id=current_user.id,
            task_id=task.id,
            social_name=social_name,
            screenshot=filename
        )

        db.session.add(submission)
        db.session.commit()

        flash("Task submitted successfully. Awaiting admin approval.", "success")
        return redirect(url_for("tasks"))

    return render_template(
        "submit_task.html",
        task=task
    )
@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():

    if request.method == "POST":

        wallet = request.form["wallet"]
        amount = float(request.form["amount"])

        if wallet == "task":
            if amount < 250 or amount > 2000:
                flash("Task Wallet withdrawal must be between ₦250 and ₦2000.", "danger")
                return redirect(url_for("withdraw"))

            if amount > current_user.task_wallet:
                flash("Insufficient Task Wallet balance.", "danger")
                return redirect(url_for("withdraw"))

        elif wallet == "referral":
            if amount < 500 or amount > 2500:
                flash("Referral Wallet withdrawal must be between ₦500 and ₦2500.", "danger")
                return redirect(url_for("withdraw"))

            if amount > current_user.referral_wallet:
                flash("Insufficient Referral Wallet balance.", "danger")
                return redirect(url_for("withdraw"))

        bank = request.form["bank"]
        account_name = request.form["account_name"]
        account_number = request.form["account_number"]

        withdrawal = Withdrawal(
            user_id=current_user.id,
            wallet=wallet,
            amount=amount,
            bank=bank,
            account_name=account_name,
            account_number=account_number,
            status="Pending"
        )

        db.session.add(withdrawal)
        db.session.commit()

        flash("Withdrawal request submitted successfully.", "success")
        return redirect(url_for("withdraw"))
    withdrawals = Withdrawal.query.filter_by(
        user_id=current_user.id
    ).order_by(Withdrawal.created_at.desc()).all()

    return render_template(
        "withdraw.html",
        withdrawals=withdrawals
    )
@app.route("/referrals")
@login_required
def referrals():

    referral_link = request.host_url + "register?ref=" + current_user.referral_code

    return render_template(
        "referrals.html",
        referral_link=referral_link,
        referral_wallet=current_user.referral_wallet,
        total_referrals=current_user.total_referrals
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin"] = True
            flash("Admin login successful.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin username or password.", "danger")
        return redirect(url_for("admin_login"))

    return render_template("admin_login.html")


def admin_required():

    return session.get("admin")
from functools import wraps


def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin"):
            flash("Please login as admin.", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/admin/dashboard")
@admin_login_required
def admin_dashboard():
    total_users = User.query.count()
    total_tasks = Task.query.count()
    total_submissions = Submission.query.count()
    pending_withdrawals = Withdrawal.query.filter_by(status="Pending").count()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_tasks=total_tasks,
        total_submissions=total_submissions,
        pending_withdrawals=pending_withdrawals
    )


@app.route("/admin/logout")
@admin_login_required
def admin_logout():
    session.pop("admin", None)
    flash("Admin logged out successfully.", "success")
    return redirect(url_for("admin_login"))
@app.route("/admin/create-task", methods=["GET", "POST"])
@admin_login_required
def create_task():

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        link = request.form["link"]
        amount = float(request.form["amount"])
        workers_needed = int(request.form["workers_needed"])

        task = Task(
            title=title,
            description=description,
            link=link,
            amount=amount,
            workers_needed=workers_needed
        )

        db.session.add(task)
        db.session.commit()

        flash("Task created successfully.", "success")
        return redirect(url_for("manage_tasks"))

    return render_template("create_task.html")


@app.route("/admin/manage-tasks")
@admin_login_required
def manage_tasks():

    tasks = Task.query.order_by(Task.created_at.desc()).all()

    return render_template(
        "manage_tasks.html",
        tasks=tasks
    )
@app.route("/admin/edit-task/<int:task_id>", methods=["GET", "POST"])
@admin_login_required
def edit_task(task_id):

    task = Task.query.get_or_404(task_id)

    if request.method == "POST":

        task.title = request.form["title"]
        task.description = request.form["description"]
        task.link = request.form["link"]
        task.amount = float(request.form["amount"])
        task.workers_needed = int(request.form["workers_needed"])

        db.session.commit()

        flash("Task updated successfully.", "success")
        return redirect(url_for("manage_tasks"))

    return render_template(
        "create_task.html",
        task=task,
        edit=True
    )


@app.route("/admin/delete-task/<int:task_id>")
@admin_login_required
def delete_task(task_id):

    task = Task.query.get_or_404(task_id)

    db.session.delete(task)
    db.session.commit()

    flash("Task deleted successfully.", "success")
    return redirect(url_for("manage_tasks"))
@app.route("/admin/submissions")
@admin_login_required
def submissions():

    submissions = (
        db.session.query(Submission, User, Task)
        .join(User, Submission.user_id == User.id)
        .join(Task, Submission.task_id == Task.id)
        .order_by(Submission.created_at.desc())
        .all()
    )

    data = []

    for submission, user, task in submissions:
        data.append({
            "id": submission.id,
            "username": user.username,
            "task_title": task.title,
            "social_name": submission.social_name,
            "screenshot": submission.screenshot,
            "status": submission.status
        })

    return render_template(
        "submissions.html",
        submissions=data
    )

@app.route("/admin/approve/<int:submission_id>")
@admin_login_required
def approve_submission(submission_id):

    submission = Submission.query.get_or_404(submission_id)

    if submission.status == "Pending":

        task = Task.query.get(submission.task_id)
        user = User.query.get(submission.user_id)

        user.task_wallet += task.amount
        submission.status = "Approved"

        # Check if user was referred and has completed 3 approved tasks
        if user.referred_by and not user.referral_reward_paid:

            approved_tasks = Submission.query.filter_by(
                user_id=user.id,
                status="Approved"
            ).count()

            if approved_tasks >= 3:
                referrer = User.query.filter_by(
                    referral_code=user.referred_by
                ).first()

                if referrer:
                    referrer.referral_wallet += 50
                    referrer.total_referrals += 1
                    user.referral_reward_paid = True

        db.session.commit()

        flash("Submission approved successfully.", "success")

    return redirect(url_for("submissions"))



@app.route("/admin/reject/<int:submission_id>")
@admin_login_required
def reject_submission(submission_id):

    submission = Submission.query.get_or_404(submission_id)

    if submission.status == "Pending":
        submission.status = "Rejected"
        db.session.commit()
        flash("Submission rejected.", "warning")

    return redirect(url_for("submissions"))


@app.route("/admin/manage-users")
@admin_login_required
def manage_users():

    users = User.query.order_by(User.created_at.desc()).all()

    return render_template(
        "manage_users.html",
        users=users
    )
@app.route("/admin/manage-withdrawals")
@admin_login_required
def manage_withdrawals():

    withdrawals = (
        db.session.query(Withdrawal, User)
        .join(User, Withdrawal.user_id == User.id)
        .filter(Withdrawal.status == "Pending")
        .order_by(Withdrawal.created_at.desc())
        .all()
    )

    data = []

    for withdrawal, user in withdrawals:
        data.append({
            "id": withdrawal.id,
            "username": user.username,
            "wallet": withdrawal.wallet,
            "amount": withdrawal.amount,
            "bank": withdrawal.bank,
            "account_name": withdrawal.account_name,
            "account_number": withdrawal.account_number,
            "status": withdrawal.status
        })

    return render_template(
        "manage_withdrawals.html",
        withdrawals=data
    )

@app.route("/admin/approve-withdrawal/<int:withdrawal_id>")
@admin_login_required
def approve_withdrawal(withdrawal_id):

    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)

    if withdrawal.status != "Pending":
        flash("This withdrawal has already been processed.", "warning")
        return redirect(url_for("manage_withdrawals"))

    user = User.query.get(withdrawal.user_id)

    if withdrawal.wallet == "task":

        if user.task_wallet < withdrawal.amount:
            flash("User has insufficient Task Wallet balance.", "danger")
            return redirect(url_for("manage_withdrawals"))

        user.task_wallet -= withdrawal.amount

    elif withdrawal.wallet == "referral":

        if user.referral_wallet < withdrawal.amount:
            flash("User has insufficient Referral Wallet balance.", "danger")
            return redirect(url_for("manage_withdrawals"))

        user.referral_wallet -= withdrawal.amount

    withdrawal.status = "Approved"

    db.session.commit()

    flash("Withdrawal approved successfully.", "success")
    return redirect(url_for("manage_withdrawals"))


@app.route("/admin/reject-withdrawal/<int:withdrawal_id>")
@admin_login_required
def reject_withdrawal(withdrawal_id):

    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)

    if withdrawal.status == "Pending":
        withdrawal.status = "Rejected"
        db.session.commit()

    flash("Withdrawal rejected.", "warning")
    return redirect(url_for("manage_withdrawals"))
@app.before_request
def create_tables():
    db.create_all()


@app.context_processor
def inject_globals():
    return {
        "website_name": "JimTask Earners"
    }


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )

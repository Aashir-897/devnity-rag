"""Authentication routes — register (with email verification), login, logout, forgot/reset password."""
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from services.email_service import send_verification_email, send_reset_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _redirect_if_logged_in():
    if current_user.is_authenticated:
        return redirect(url_for("index"))


# ── Login ──────────────────────────────────────────────────────────────────────


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    r = _redirect_if_logged_in()
    if r: return r

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html")

        if not user.is_verified:
            flash("Please verify your email first. Check your inbox.", "error")
            return render_template("auth/login.html")

        login_user(user)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("index"))

    return render_template("auth/login.html")


# ── Register ───────────────────────────────────────────────────────────────────


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    r = _redirect_if_logged_in()
    if r: return r

    if request.method == "POST":
        email            = request.form.get("email", "").strip().lower()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("auth/register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return render_template("auth/register.html")

        user = User(email=email)
        user.set_password(password)
        user.verification_token = secrets.token_urlsafe(48)
        user.is_verified = False
        db.session.add(user)
        db.session.commit()

        send_verification_email(email, user.verification_token)
        flash("Account created! Check your email to verify.", "success")
        return redirect(url_for("auth.check_email"))

    return render_template("auth/register.html")


# ── Email Verification ─────────────────────────────────────────────────────────


@auth_bp.route("/verify/<token>")
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash("Invalid or expired verification link.", "error")
        return redirect(url_for("auth.login"))

    user.is_verified = True
    user.verification_token = None
    db.session.commit()

    flash("Email verified! You can now log in.", "success")
    return redirect(url_for("auth.login"))


# ── Check Email Page ───────────────────────────────────────────────────────────


@auth_bp.route("/check-email")
def check_email():
    return render_template("auth/check_email.html")


# ── Forgot Password ────────────────────────────────────────────────────────────


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            user.reset_token = secrets.token_urlsafe(48)
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            send_reset_email(email, user.reset_token)

        flash("If that email is registered, a reset link has been sent.", "success")
        return redirect(url_for("auth.check_email"))

    return render_template("auth/forgot_password.html")


# ── Reset Password ─────────────────────────────────────────────────────────────


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        flash("Invalid or expired reset link.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not password:
            flash("Password is required.", "error")
            return render_template("auth/reset_password.html", token=token)

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("auth/reset_password.html", token=token)

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("auth/reset_password.html", token=token)

        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()

        flash("Password reset successful! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)


# ── Logout ──────────────────────────────────────────────────────────────────────


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

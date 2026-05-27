"""SMTP email service — send verification, password reset, and general emails."""
import os
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM, MAIL_FROM_NAME, APP_URL

EMAIL_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "email_debug.log")


def _log(msg: str):
    with open(EMAIL_LOG, "a") as f:
        f.write(f"{msg}\n")


def send_email(to: str, subject: str, html_body: str) -> bool:
    _log(f"send_email to={to} subject={subject}")
    _log(f"  config: SMTP_SERVER={SMTP_SERVER} SMTP_USERNAME={SMTP_USERNAME} MAIL_FROM={MAIL_FROM}")
    if not SMTP_SERVER or not SMTP_USERNAME:
        _log("  SKIP — SMTP_SERVER or SMTP_USERNAME empty")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL(SMTP_SERVER, 465, timeout=10) as server:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(MAIL_FROM, [to], msg.as_string())
        _log("  SUCCESS")
        return True
    except Exception as e:
        _log(f"  FAILED: {e}\n{traceback.format_exc()}")
        return False


def send_verification_email(user_email: str, token: str) -> bool:
    link = f"{APP_URL}/auth/verify/{token}"
    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:24px;background:#f8fafc">
<div style="max-width:480px;margin:0 auto;background:white;border-radius:12px;padding:32px;border:1px solid #e2e8f0">
<h2 style="margin:0 0 8px;color:#1E1B4B">Welcome to Devnity AI</h2>
<p style="color:#64748b;margin-bottom:20px">Confirm your email to start using PDF intelligence.</p>
<a href="{link}" style="display:inline-block;padding:12px 24px;background:#1E1B4B;color:white;text-decoration:none;border-radius:8px;font-weight:600">Verify Email</a>
<p style="color:#94a3b8;font-size:12px;margin-top:20px">Or paste this link: {link}</p>
</div></body></html>"""
    return send_email(user_email, "Verify your Devnity AI account", html)


def send_reset_email(user_email: str, token: str) -> bool:
    link = f"{APP_URL}/auth/reset-password/{token}"
    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:24px;background:#f8fafc">
<div style="max-width:480px;margin:0 auto;background:white;border-radius:12px;padding:32px;border:1px solid #e2e8f0">
<h2 style="margin:0 0 8px;color:#1E1B4B">Reset Your Password</h2>
<p style="color:#64748b;margin-bottom:20px">Click below to set a new password. This link expires in 1 hour.</p>
<a href="{link}" style="display:inline-block;padding:12px 24px;background:#1E1B4B;color:white;text-decoration:none;border-radius:8px;font-weight:600">Reset Password</a>
<p style="color:#94a3b8;font-size:12px;margin-top:20px">Or paste this link: {link}</p>
</div></body></html>"""
    return send_email(user_email, "Password reset — Devnity AI", html)

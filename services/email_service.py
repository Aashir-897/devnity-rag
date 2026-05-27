"""Email service — proxies via DO relay."""
import os
import requests

MAIL_RELAY_URL = "https://rag.devnity.me/send-email"


def send_email(to: str, subject: str, html_body: str) -> bool:
    try:
        resp = requests.post(MAIL_RELAY_URL, json={
            "to": to, "subject": subject, "html": html_body
        }, timeout=15)
        return resp.status_code == 200 and resp.json().get("sent")
    except Exception as e:
        print(f"Email relay failed: {e}")
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

"""Email relay — receives POST from HF Spaces, forwards to LarkSuite via SMTP_SSL."""
import os
from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SMTP_SERVER   = "smtp.larksuite.com"
SMTP_PORT     = 465
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM     = os.getenv("MAIL_FROM", "noreply@devnity.me")


@app.route("/send-email", methods=["POST"])
def send_email():
    data = request.json
    to = data.get("to")
    subject = data.get("subject")
    html = data.get("html")

    if not to or not subject or not html:
        return jsonify({"sent": False, "error": "Missing fields"}), 400

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Devnity AI <{MAIL_FROM}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(MAIL_FROM, [to], msg.as_string())

        return jsonify({"sent": True})
    except Exception as e:
        return jsonify({"sent": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)

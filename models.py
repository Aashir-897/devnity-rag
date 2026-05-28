"""SQLAlchemy models — User and Document."""
import uuid
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email               = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash       = db.Column(db.String(256), nullable=False)
    is_verified         = db.Column(db.Boolean, default=False)
    verification_token  = db.Column(db.String(100), nullable=True, index=True)
    reset_token         = db.Column(db.String(100), nullable=True, index=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    created_at          = db.Column(db.DateTime, server_default=db.func.now())

    documents = db.relationship("Document", backref="owner", lazy="dynamic")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Document(db.Model):
    __tablename__ = "documents"

    id            = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    original_name = db.Column(db.String(255), nullable=False)
    storage_key   = db.Column(db.String(512), default="")
    summary       = db.Column(db.Text, default="")
    full_text     = db.Column(db.Text, default="")
    lines_data    = db.Column(db.JSON, default=dict)
    num_chunks    = db.Column(db.Integer, default=0)
    total_pages   = db.Column(db.Integer, default=0)
    status        = db.Column(db.String(20), default="processing")
    mcqs          = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, default="")
    created_at    = db.Column(db.DateTime, server_default=db.func.now())

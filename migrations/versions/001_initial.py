"""Create users and documents tables."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False, index=True),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default="0", nullable=True),
        sa.Column("verification_token", sa.String(length=100), nullable=True, index=True),
        sa.Column("reset_token", sa.String(length=100), nullable=True, index=True),
        sa.Column("reset_token_expires", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), server_default="", nullable=True),
        sa.Column("summary", sa.Text(), server_default="", nullable=True),
        sa.Column("full_text", sa.Text(), server_default="", nullable=True),
        sa.Column("lines_data", sa.JSON(), nullable=True),
        sa.Column("num_chunks", sa.Integer(), server_default="0", nullable=True),
        sa.Column("total_pages", sa.Integer(), server_default="0", nullable=True),
        sa.Column("status", sa.String(length=20), server_default="processing", nullable=True),
        sa.Column("mcqs", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), server_default="", nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("users")

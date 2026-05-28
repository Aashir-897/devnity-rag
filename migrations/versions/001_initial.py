"""Create users and documents tables."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER AUTO_INCREMENT,
            email VARCHAR(120) NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            is_verified BOOLEAN DEFAULT 0,
            verification_token VARCHAR(100),
            reset_token VARCHAR(100),
            reset_token_expires DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id VARCHAR(36),
            user_id INTEGER NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            storage_key VARCHAR(512) DEFAULT '',
            summary TEXT DEFAULT '',
            full_text TEXT DEFAULT '',
            lines_data JSON,
            num_chunks INTEGER DEFAULT 0,
            total_pages INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'processing',
            mcqs JSON,
            error_message TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    op.create_unique_constraint(None, "users", ["email"])
    op.create_index(None, "users", ["verification_token"])
    op.create_index(None, "users", ["reset_token"])
    op.create_index(None, "documents", ["user_id"])


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("users")

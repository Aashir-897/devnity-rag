"""Add doc_type column to documents table if missing."""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

revision: str = "004_add_doc_type"
down_revision: Union[str, None] = "003_add_qa_pairs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'documents' AND COLUMN_NAME = 'doc_type'"
    ))
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE documents ADD COLUMN doc_type VARCHAR(20) DEFAULT 'unknown'")


def downgrade() -> None:
    op.execute("ALTER TABLE documents DROP COLUMN doc_type")

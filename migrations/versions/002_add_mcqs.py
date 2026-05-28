"""Add mcqs column to documents table if missing."""
from typing import Sequence, Union
from alembic import op

revision: str = "002_add_mcqs"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'documents' AND COLUMN_NAME = 'mcqs'"
    )
    if result.fetchone()[0] == 0:
        op.execute("ALTER TABLE documents ADD COLUMN mcqs JSON")


def downgrade() -> None:
    op.execute("ALTER TABLE documents DROP COLUMN mcqs")

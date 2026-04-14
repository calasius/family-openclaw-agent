"""add material extraction cache columns"""

from alembic import op
import sqlalchemy as sa


revision = "20260413_000002"
down_revision = "20260408_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task_materials", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column("task_materials", sa.Column("extracted_text_source", sa.String(), nullable=True))
    op.add_column("task_materials", sa.Column("extracted_text_updated_at", sa.String(), nullable=True))
    op.add_column(
        "task_materials",
        sa.Column("extracted_from_task_source_updated_at", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("task_materials", "extracted_from_task_source_updated_at")
    op.drop_column("task_materials", "extracted_text_updated_at")
    op.drop_column("task_materials", "extracted_text_source")
    op.drop_column("task_materials", "extracted_text")

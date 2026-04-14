"""initial schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260408_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("external_id", sa.String(), primary_key=True),
        sa.Column("course_id", sa.String(), nullable=False),
        sa.Column("course_name", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("source_updated_at", sa.String(), nullable=False),
        sa.Column("synced_at", sa.String(), nullable=False),
    )
    op.create_table(
        "task_materials",
        sa.Column("material_id", sa.String(), primary_key=True),
        sa.Column("task_external_id", sa.String(), sa.ForeignKey("tasks.external_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("material_type", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("drive_file_id", sa.String(), nullable=True),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("synced_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("task_materials")
    op.drop_table("tasks")

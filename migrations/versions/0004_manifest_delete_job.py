"""Add manifest delete jobs."""

from alembic import op

revision = "0004_manifest_delete_job"
down_revision = "0003_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'MANIFEST_DELETE'")


def downgrade() -> None:
    # PostgreSQL enum values intentionally remain; removing enum values requires type recreation.
    pass

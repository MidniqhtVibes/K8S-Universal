"""Track the configuration and VM IDs actually applied by Terraform."""

from alembic import op
import sqlalchemy as sa


revision = "0006_applied_cluster_state"
down_revision = "0005_job_recovery_ansible"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clusters", sa.Column("applied_hash", sa.String(length=64), nullable=True))
    op.add_column("clusters", sa.Column("applied_vm_ids", sa.JSON(), nullable=True))
    # Existing READY clusters completed Terraform and Ansible in an older
    # version, so their current config hash is a safe compatibility backfill.
    op.execute("UPDATE clusters SET applied_hash = config_hash WHERE status = 'READY'")


def downgrade() -> None:
    op.drop_column("clusters", "applied_vm_ids")
    op.drop_column("clusters", "applied_hash")

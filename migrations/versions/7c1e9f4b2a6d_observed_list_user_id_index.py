"""Add index on observed_lists.user_id

Revision ID: 7c1e9f4b2a6d
Revises: 9f2a3b1c4d5e
Create Date: 2026-02-10 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c1e9f4b2a6d'
down_revision = '9f2a3b1c4d5e'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('observed_lists')}
    if 'ix_observed_lists_user_id' not in existing_indexes:
        with op.batch_alter_table('observed_lists', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_observed_lists_user_id'), ['user_id'], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('observed_lists')}
    if 'ix_observed_lists_user_id' in existing_indexes:
        with op.batch_alter_table('observed_lists', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_observed_lists_user_id'))

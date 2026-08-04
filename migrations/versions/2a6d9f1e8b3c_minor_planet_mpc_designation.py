"""Minor planet MPC designation

Revision ID: 2a6d9f1e8b3c
Revises: c3d9a12e8f7b
Create Date: 2026-08-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a6d9f1e8b3c'
down_revision = 'c3d9a12e8f7b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('minor_planets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mpc_designation', sa.String(length=16), nullable=True))
        batch_op.create_index(batch_op.f('ix_minor_planets_mpc_designation'), ['mpc_designation'], unique=False)


def downgrade():
    with op.batch_alter_table('minor_planets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_minor_planets_mpc_designation'))
        batch_op.drop_column('mpc_designation')

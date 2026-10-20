"""Near-Earth asteroids: computed peak brightness and its time

Revision ID: f3b8d2a6c4e1
Revises: e5a1c7d3b9f2
Create Date: 2026-10-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b8d2a6c4e1'
down_revision = 'e5a1c7d3b9f2'
branch_labels = None
depends_on = None


def upgrade():
    # Existing rows get the values on the next daily update.
    with op.batch_alter_table('neo_close_approaches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('peak_mag', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('peak_time', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('neo_close_approaches', schema=None) as batch_op:
        batch_op.drop_column('peak_time')
        batch_op.drop_column('peak_mag')

"""Observing session is_active

Revision ID: f0756285e3c6
Revises: e1a24e18c48f
Create Date: 2023-09-21 21:22:36.548298

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f0756285e3c6'
down_revision = 'e1a24e18c48f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observing_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observing_sessions', schema=None) as batch_op:
        batch_op.drop_column('is_active')

    # ### end Alembic commands ###
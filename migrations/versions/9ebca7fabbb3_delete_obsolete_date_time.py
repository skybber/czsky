"""delete obsolete date_time

Revision ID: 9ebca7fabbb3
Revises: 59e984573cf3
Create Date: 2022-01-07 20:19:23.992230

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9ebca7fabbb3'
down_revision = '59e984573cf3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.drop_column('date_time')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('date_time', sa.DATETIME(), nullable=True))

    # ### end Alembic commands ###
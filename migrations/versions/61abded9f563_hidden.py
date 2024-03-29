"""hidden

Revision ID: 61abded9f563
Revises: 130e21bec8a9
Create Date: 2022-02-02 16:45:21.895231

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '61abded9f563'
down_revision = '130e21bec8a9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dso_lists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hidden', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dso_lists', schema=None) as batch_op:
        batch_op.drop_column('hidden')

    # ### end Alembic commands ###

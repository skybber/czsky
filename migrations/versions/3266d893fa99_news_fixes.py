"""News fixes

Revision ID: 3266d893fa99
Revises: a01295e9cae9
Create Date: 2021-04-03 19:37:03.208966

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3266d893fa99'
down_revision = 'a01295e9cae9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('news', schema=None) as batch_op:
        batch_op.drop_index('ix_news_dec')
        batch_op.drop_index('ix_news_ra')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('news', schema=None) as batch_op:
        batch_op.create_index('ix_news_ra', ['ra'], unique=False)
        batch_op.create_index('ix_news_dec', ['dec'], unique=False)

    # ### end Alembic commands ###
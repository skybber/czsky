"""Lang code in news

Revision ID: c064e129d352
Revises: 016d52caf6cc
Create Date: 2021-11-13 12:35:33.453012

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c064e129d352'
down_revision = '016d52caf6cc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('news', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lang_code', sa.String(length=6), nullable=True))
        batch_op.create_index(batch_op.f('ix_news_is_released'), ['is_released'], unique=False)
        batch_op.drop_index('ix_news_title')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('news', schema=None) as batch_op:
        batch_op.create_index('ix_news_title', ['title'], unique=False)
        batch_op.drop_index(batch_op.f('ix_news_is_released'))
        batch_op.drop_column('lang_code')

    # ### end Alembic commands ###
"""Stars

Revision ID: a58e53077779
Revises: 9d54e8c4a577
Create Date: 2020-02-20 19:21:31.813112

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a58e53077779'
down_revision = '9d54e8c4a577'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('stars',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('hr', sa.Integer(), nullable=True),
    sa.Column('bayer_flamsteed', sa.String(length=10), nullable=True),
    sa.Column('hd', sa.Integer(), nullable=True),
    sa.Column('sao', sa.Integer(), nullable=True),
    sa.Column('fk5', sa.Integer(), nullable=True),
    sa.Column('multiple', sa.String(length=1), nullable=True),
    sa.Column('ads', sa.String(length=5), nullable=True),
    sa.Column('ads_comp', sa.String(length=2), nullable=True),
    sa.Column('var_id', sa.String(length=9), nullable=True),
    sa.Column('ra', sa.Float(), nullable=True),
    sa.Column('dec', sa.Float(), nullable=True),
    sa.Column('mag', sa.Float(), nullable=True),
    sa.Column('bv', sa.Float(), nullable=True),
    sa.Column('sp_type', sa.String(length=20), nullable=True),
    sa.Column('dmag', sa.Float(), nullable=True),
    sa.Column('sep', sa.Float(), nullable=True),
    sa.Column('mult_id', sa.String(length=4), nullable=True),
    sa.Column('mult_cnt', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stars_bayer_flamsteed'), 'stars', ['bayer_flamsteed'], unique=False)
    op.create_index(op.f('ix_stars_fk5'), 'stars', ['fk5'], unique=True)
    op.create_index(op.f('ix_stars_hd'), 'stars', ['hd'], unique=True)
    op.create_index(op.f('ix_stars_hr'), 'stars', ['hr'], unique=True)
    op.create_index(op.f('ix_stars_sao'), 'stars', ['sao'], unique=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_stars_sao'), table_name='stars')
    op.drop_index(op.f('ix_stars_hr'), table_name='stars')
    op.drop_index(op.f('ix_stars_hd'), table_name='stars')
    op.drop_index(op.f('ix_stars_fk5'), table_name='stars')
    op.drop_index(op.f('ix_stars_bayer_flamsteed'), table_name='stars')
    op.drop_table('stars')
    # ### end Alembic commands ###
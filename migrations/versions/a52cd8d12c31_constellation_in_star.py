"""Constellation in star

Revision ID: a52cd8d12c31
Revises: 95149d04c7cd
Create Date: 2020-02-22 12:56:26.585914

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a52cd8d12c31'
down_revision = '95149d04c7cd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('stars', schema=None) as batch_op:
        batch_op.add_column(sa.Column('constellation_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_stars_constellation_id_constellations'), 'constellations', ['constellation_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('stars', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_stars_constellation_id_constellations'), type_='foreignkey')
        batch_op.drop_column('constellation_id')

    # ### end Alembic commands ###
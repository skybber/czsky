"""Moinor planets in observ

Revision ID: cadeea9b1c48
Revises: 6a6729c48b67
Create Date: 2022-05-15 12:26:39.887882

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cadeea9b1c48'
down_revision = '6a6729c48b67'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('minor_planet_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_observations_minor_planet_id_minor_planets'), 'minor_planets', ['minor_planet_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_observations_minor_planet_id_minor_planets'), type_='foreignkey')
        batch_op.drop_column('minor_planet_id')

    # ### end Alembic commands ###
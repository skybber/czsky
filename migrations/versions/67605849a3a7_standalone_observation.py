"""Standalone observation

Revision ID: 67605849a3a7
Revises: 5b7407e4ef5c
Create Date: 2022-03-30 18:45:12.392178

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '67605849a3a7'
down_revision = '5b7407e4ef5c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('location_position', sa.String(length=256), nullable=True))
        batch_op.alter_column('observing_session_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_observations_location_id'), ['location_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_observations_location_id_locations'), 'locations', ['location_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_observations_location_id_locations'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_observations_location_id'))
        batch_op.alter_column('observing_session_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('location_position')
        batch_op.drop_column('location_id')

    # ### end Alembic commands ###

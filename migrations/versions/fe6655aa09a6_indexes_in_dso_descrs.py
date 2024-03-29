"""Indexes in dso descrs

Revision ID: fe6655aa09a6
Revises: 61abded9f563
Create Date: 2022-02-13 11:34:01.167698

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fe6655aa09a6'
down_revision = '61abded9f563'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('session_plan_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('item_type', sa.Enum('DSO', 'DBL_STAR', 'MINOR_PLANET', 'COMET', name='sessionplanitemtype'), nullable=True))
        batch_op.add_column(sa.Column('double_star_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('minor_planet_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('comet_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_session_plan_items_comet_id_comets'), 'comets', ['comet_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_session_plan_items_minor_planet_id_minor_planets'), 'minor_planets', ['minor_planet_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_session_plan_items_double_star_id_double_stars'), 'double_stars', ['double_star_id'], ['id'])

    with op.batch_alter_table('user_dso_aperture_descriptions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_dso_aperture_descriptions_dso_id'), ['dso_id'], unique=False)

    with op.batch_alter_table('user_dso_descriptions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_dso_descriptions_dso_id'), ['dso_id'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_dso_descriptions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_dso_descriptions_dso_id'))

    with op.batch_alter_table('user_dso_aperture_descriptions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_dso_aperture_descriptions_dso_id'))

    with op.batch_alter_table('session_plan_items', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_session_plan_items_double_star_id_double_stars'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_session_plan_items_minor_planet_id_minor_planets'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_session_plan_items_comet_id_comets'), type_='foreignkey')
        batch_op.drop_column('comet_id')
        batch_op.drop_column('minor_planet_id')
        batch_op.drop_column('double_star_id')
        batch_op.drop_column('item_type')

    # ### end Alembic commands ###

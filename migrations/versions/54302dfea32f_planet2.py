"""Planet2

Revision ID: 54302dfea32f
Revises: 34baace6b42d
Create Date: 2022-10-16 11:18:07.124929

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '54302dfea32f'
down_revision = '34baace6b42d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.create_foreign_key(batch_op.f('fk_observations_planet_id_planets'), 'planets', ['planet_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_observations_planet_id_planets'), type_='foreignkey')

    # ### end Alembic commands ###
"""double_star_id in star description

Revision ID: b4a752d2ae5e
Revises: 6ed23def7e1a
Create Date: 2022-01-16 14:18:24.688354

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4a752d2ae5e'
down_revision = '6ed23def7e1a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_star_descriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('double_star_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_user_star_descriptions_double_star_id_double_stars'), 'double_stars', ['double_star_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_star_descriptions', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_user_star_descriptions_double_star_id_double_stars'), type_='foreignkey')
        batch_op.drop_column('double_star_id')

    # ### end Alembic commands ###

"""StarDescr link to star

Revision ID: 95149d04c7cd
Revises: 85735fbf6752
Create Date: 2020-02-22 08:35:52.282847

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95149d04c7cd'
down_revision = '85735fbf6752'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_star_descriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('star_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_user_star_descriptions_star_id_stars'), 'stars', ['star_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_star_descriptions', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_user_star_descriptions_star_id_stars'), type_='foreignkey')
        batch_op.drop_column('star_id')

    # ### end Alembic commands ###
"""Imp hist in location

Revision ID: 8cf4d5343ade
Revises: a1294e02f7f4
Create Date: 2022-05-07 11:35:56.658604

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8cf4d5343ade'
down_revision = 'a1294e02f7f4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('import_history_rec_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_locations_import_history_rec_id'), ['import_history_rec_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_locations_import_history_rec_id_import_history_recs'), 'import_history_recs', ['import_history_rec_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_locations_import_history_rec_id_import_history_recs'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_locations_import_history_rec_id'))
        batch_op.drop_column('import_history_rec_id')

    # ### end Alembic commands ###

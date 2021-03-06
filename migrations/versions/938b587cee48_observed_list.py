"""Observed list

Revision ID: 938b587cee48
Revises: dd8d565e95d9
Create Date: 2020-10-10 19:19:42.110814

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '938b587cee48'
down_revision = 'dd8d565e95d9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('observed_lists',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('update_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_observed_lists_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_observed_lists'))
    )
    op.create_table('observed_list_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('observed_list_id', sa.Integer(), nullable=False),
    sa.Column('dso_id', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('update_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['dso_id'], ['deepsky_objects.id'], name=op.f('fk_observed_list_items_dso_id_deepsky_objects')),
    sa.ForeignKeyConstraint(['observed_list_id'], ['observed_lists.id'], name=op.f('fk_observed_list_items_observed_list_id_observed_lists')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_observed_list_items'))
    )
    with op.batch_alter_table('wish_list_items', schema=None) as batch_op:
        batch_op.drop_column('notes')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('wish_list_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.TEXT(), nullable=True))

    op.drop_table('observed_list_items')
    op.drop_table('observed_lists')
    # ### end Alembic commands ###

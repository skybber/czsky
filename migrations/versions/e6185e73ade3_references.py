"""References

Revision ID: e6185e73ade3
Revises: 5e6cf999af0a
Create Date: 2020-02-09 13:52:07.298826

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6185e73ade3'
down_revision = '5e6cf999af0a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('sky_list',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=True),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('create_by', sa.Integer(), nullable=True),
    sa.Column('update_by', sa.Integer(), nullable=True),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('update_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['create_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['update_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sky_list_name'), 'sky_list', ['name'], unique=False)
    op.create_table('session_plans',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.Column('for_date', sa.DateTime(), nullable=True),
    sa.Column('sky_list_id', sa.Integer(), nullable=False),
    sa.Column('create_by', sa.Integer(), nullable=True),
    sa.Column('update_by', sa.Integer(), nullable=True),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('update_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['create_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.ForeignKeyConstraint(['sky_list_id'], ['sky_list.id'], ),
    sa.ForeignKeyConstraint(['update_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_plans_title'), 'session_plans', ['title'], unique=False)
    op.create_table('sky_list_item',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sky_list_id', sa.Integer(), nullable=False),
    sa.Column('dso_id', sa.Integer(), nullable=True),
    sa.Column('order', sa.Integer(), nullable=True),
    sa.Column('create_by', sa.Integer(), nullable=True),
    sa.Column('update_by', sa.Integer(), nullable=True),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('update_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['create_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['dso_id'], ['deepsky_objects.id'], ),
    sa.ForeignKeyConstraint(['sky_list_id'], ['sky_list.id'], ),
    sa.ForeignKeyConstraint(['update_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('wish_lists',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('sky_list_id', sa.Integer(), nullable=False),
    sa.Column('create_by', sa.Integer(), nullable=True),
    sa.Column('update_by', sa.Integer(), nullable=True),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('update_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['create_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sky_list_id'], ['sky_list.id'], ),
    sa.ForeignKeyConstraint(['update_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('wish_lists')
    op.drop_table('sky_list_item')
    op.drop_index(op.f('ix_session_plans_title'), table_name='session_plans')
    op.drop_table('session_plans')
    op.drop_index(op.f('ix_sky_list_name'), table_name='sky_list')
    op.drop_table('sky_list')
    # ### end Alembic commands ###
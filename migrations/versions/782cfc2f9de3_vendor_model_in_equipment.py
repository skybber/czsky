"""Vendor+Model in equipment

Revision ID: 782cfc2f9de3
Revises: f6d095c9f8ef
Create Date: 2021-12-30 19:04:16.753163

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '782cfc2f9de3'
down_revision = 'f6d095c9f8ef'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('eyepieces', schema=None) as batch_op:
        batch_op.add_column(sa.Column('model', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('vendor', sa.String(length=128), nullable=True))
        batch_op.create_index(batch_op.f('ix_eyepieces_model'), ['model'], unique=False)
        batch_op.create_index(batch_op.f('ix_eyepieces_vendor'), ['vendor'], unique=False)

    with op.batch_alter_table('filters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('model', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('vendor', sa.String(length=128), nullable=True))
        batch_op.create_index(batch_op.f('ix_filters_model'), ['model'], unique=False)
        batch_op.create_index(batch_op.f('ix_filters_vendor'), ['vendor'], unique=False)

    with op.batch_alter_table('telescopes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('model', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('vendor', sa.String(length=128), nullable=True))
        batch_op.create_index(batch_op.f('ix_telescopes_model'), ['model'], unique=False)
        batch_op.create_index(batch_op.f('ix_telescopes_vendor'), ['vendor'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('telescopes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_telescopes_vendor'))
        batch_op.drop_index(batch_op.f('ix_telescopes_model'))
        batch_op.drop_column('vendor')
        batch_op.drop_column('model')

    with op.batch_alter_table('filters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_filters_vendor'))
        batch_op.drop_index(batch_op.f('ix_filters_model'))
        batch_op.drop_column('vendor')
        batch_op.drop_column('model')

    with op.batch_alter_table('eyepieces', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_eyepieces_vendor'))
        batch_op.drop_index(batch_op.f('ix_eyepieces_model'))
        batch_op.drop_column('vendor')
        batch_op.drop_column('model')

    # ### end Alembic commands ###
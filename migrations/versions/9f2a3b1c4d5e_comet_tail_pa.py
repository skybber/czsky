"""Add comet tail position angle

Revision ID: 9f2a3b1c4d5e
Revises: 81b98c833b6b
Create Date: 2026-02-07 13:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9f2a3b1c4d5e'
down_revision = '81b98c833b6b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('comets', sa.Column('cur_tail_pa', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('comets', 'cur_tail_pa')

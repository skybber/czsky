"""Support administrator-managed comet elements.

Revision ID: 4b7d2e9a6c10
Revises: 2a6d9f1e8b3c
"""
from alembic import op
import sqlalchemy as sa


revision = '4b7d2e9a6c10'
down_revision = '2a6d9f1e8b3c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('comets', sa.Column('is_manual', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('comets', 'is_manual')

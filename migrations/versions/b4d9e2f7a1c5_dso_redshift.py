"""Deepsky objects: redshift

Revision ID: b4d9e2f7a1c5
Revises: c2e8f1a4b6d3
Create Date: 2026-10-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4d9e2f7a1c5'
down_revision = 'c2e8f1a4b6d3'
branch_labels = None
depends_on = None


def upgrade():
    # Filled by quasar import (flask tmp_import_quasars), other objects stay null.
    with op.batch_alter_table('deepsky_objects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('redshift', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('deepsky_objects', schema=None) as batch_op:
        batch_op.drop_column('redshift')

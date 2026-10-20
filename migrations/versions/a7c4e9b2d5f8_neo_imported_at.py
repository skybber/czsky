"""Minor planets: time the daily NEA update imported the row

Revision ID: a7c4e9b2d5f8
Revises: f3b8d2a6c4e1
Create Date: 2026-10-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c4e9b2d5f8'
down_revision = 'f3b8d2a6c4e1'
branch_labels = None
depends_on = None


def upgrade():
    # Existing rows stay null: their origin is unknown, so they are never deleted automatically.
    with op.batch_alter_table('minor_planets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('neo_imported_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('minor_planets', schema=None) as batch_op:
        batch_op.drop_column('neo_imported_at')

"""Chart drawings

Revision ID: b7e2d4f1a9c3
Revises: 5d2f8a3c9b61
Create Date: 2026-10-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e2d4f1a9c3'
down_revision = '5d2f8a3c9b61'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('chart_drawings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('definition', sa.Text(), nullable=False),
    sa.Column('item_count', sa.Integer(), nullable=False),
    sa.Column('center_ra', sa.Float(), nullable=True),
    sa.Column('center_dec', sa.Float(), nullable=True),
    sa.Column('fld_size', sa.Float(), nullable=True),
    sa.Column('is_public', sa.Boolean(), nullable=False),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.Column('update_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_chart_drawings_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chart_drawings'))
    )
    with op.batch_alter_table('chart_drawings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chart_drawings_name'), ['name'], unique=False)
        batch_op.create_index(batch_op.f('ix_chart_drawings_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('chart_drawings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chart_drawings_user_id'))
        batch_op.drop_index(batch_op.f('ix_chart_drawings_name'))

    op.drop_table('chart_drawings')

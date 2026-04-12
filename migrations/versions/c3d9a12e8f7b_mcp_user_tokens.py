"""Add mcp_user_tokens table

Revision ID: c3d9a12e8f7b
Revises: 7c1e9f4b2a6d
Create Date: 2026-04-12 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d9a12e8f7b'
down_revision = '7c1e9f4b2a6d'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'mcp_user_tokens' not in existing_tables:
        op.create_table(
            'mcp_user_tokens',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('token_id', sa.String(length=32), nullable=False),
            sa.Column('token_name', sa.String(length=128), nullable=False),
            sa.Column('token_prefix', sa.String(length=16), nullable=False),
            sa.Column('token_hash', sa.String(length=255), nullable=False),
            sa.Column('scope', sa.String(length=256), nullable=False),
            sa.Column('last_used_date', sa.DateTime(), nullable=True),
            sa.Column('expires_date', sa.DateTime(), nullable=True),
            sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('create_date', sa.DateTime(), nullable=True),
            sa.Column('update_date', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ['user_id'],
                ['users.id'],
                name=op.f('fk_mcp_user_tokens_user_id_users'),
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_mcp_user_tokens')),
        )

    existing_indexes = {idx['name'] for idx in inspector.get_indexes('mcp_user_tokens')}
    if 'ix_mcp_user_tokens_user_id' not in existing_indexes:
        with op.batch_alter_table('mcp_user_tokens', schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f('ix_mcp_user_tokens_user_id'),
                ['user_id'],
                unique=False,
            )

    if 'ix_mcp_user_tokens_token_id' not in existing_indexes:
        with op.batch_alter_table('mcp_user_tokens', schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f('ix_mcp_user_tokens_token_id'),
                ['token_id'],
                unique=True,
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if 'mcp_user_tokens' in existing_tables:
        op.drop_table('mcp_user_tokens')

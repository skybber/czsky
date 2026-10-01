"""Add MCP OAuth refresh token history

Revision ID: 5d2f8a3c9b61
Revises: 9e4b1c7a2d58
Create Date: 2026-10-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d2f8a3c9b61'
down_revision = '9e4b1c7a2d58'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'mcp_oauth_refresh_token_history' not in existing_tables:
        op.create_table(
            'mcp_oauth_refresh_token_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('token_row_id', sa.Integer(), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('create_date', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ['token_row_id'],
                ['mcp_user_tokens.id'],
                name=op.f('fk_mcp_oauth_refresh_token_history_token_row_id_mcp_user_tokens'),
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_mcp_oauth_refresh_token_history')),
        )
        with op.batch_alter_table('mcp_oauth_refresh_token_history', schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f('ix_mcp_oauth_refresh_token_history_token_row_id'),
                ['token_row_id'],
                unique=False,
            )
            batch_op.create_index(
                batch_op.f('ix_mcp_oauth_refresh_token_history_token_hash'),
                ['token_hash'],
                unique=True,
            )

    # Refresh token hashes switched from werkzeug password hash to SHA-256;
    # refresh tokens issued before this revision can no longer be verified.
    if 'mcp_user_tokens' in existing_tables:
        op.execute("UPDATE mcp_user_tokens SET refresh_token_hash = NULL WHERE oauth_client_id IS NOT NULL")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'mcp_oauth_refresh_token_history' in set(inspector.get_table_names()):
        op.drop_table('mcp_oauth_refresh_token_history')

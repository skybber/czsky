"""Add MCP OAuth clients, authorization codes and OAuth token columns

Revision ID: 9e4b1c7a2d58
Revises: 4b7d2e9a6c10
Create Date: 2026-10-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9e4b1c7a2d58'
down_revision = '4b7d2e9a6c10'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'mcp_oauth_clients' not in existing_tables:
        op.create_table(
            'mcp_oauth_clients',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('client_id', sa.String(length=64), nullable=False),
            sa.Column('client_name', sa.String(length=128), nullable=True),
            sa.Column('client_secret_hash', sa.String(length=255), nullable=True),
            sa.Column('token_endpoint_auth_method', sa.String(length=32), nullable=False),
            sa.Column('redirect_uris', sa.Text(), nullable=False),
            sa.Column('scope', sa.String(length=256), nullable=True),
            sa.Column('create_date', sa.DateTime(), nullable=True),
            sa.Column('last_used_date', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_mcp_oauth_clients')),
        )
        with op.batch_alter_table('mcp_oauth_clients', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_mcp_oauth_clients_client_id'), ['client_id'], unique=True)

    if 'mcp_oauth_authorization_codes' not in existing_tables:
        op.create_table(
            'mcp_oauth_authorization_codes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code_hash', sa.String(length=64), nullable=False),
            sa.Column('client_id', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('redirect_uri', sa.String(length=512), nullable=False),
            sa.Column('scope', sa.String(length=256), nullable=False),
            sa.Column('code_challenge', sa.String(length=128), nullable=False),
            sa.Column('resource', sa.String(length=512), nullable=True),
            sa.Column('expires_date', sa.DateTime(), nullable=False),
            sa.Column('is_used', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('token_row_id', sa.Integer(), nullable=True),
            sa.Column('create_date', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ['user_id'],
                ['users.id'],
                name=op.f('fk_mcp_oauth_authorization_codes_user_id_users'),
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_mcp_oauth_authorization_codes')),
        )
        with op.batch_alter_table('mcp_oauth_authorization_codes', schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f('ix_mcp_oauth_authorization_codes_code_hash'),
                ['code_hash'],
                unique=True,
            )

    existing_columns = {col['name'] for col in inspector.get_columns('mcp_user_tokens')}
    with op.batch_alter_table('mcp_user_tokens', schema=None) as batch_op:
        if 'oauth_client_id' not in existing_columns:
            batch_op.add_column(sa.Column('oauth_client_id', sa.String(length=64), nullable=True))
            batch_op.create_index(batch_op.f('ix_mcp_user_tokens_oauth_client_id'), ['oauth_client_id'], unique=False)
        if 'refresh_token_hash' not in existing_columns:
            batch_op.add_column(sa.Column('refresh_token_hash', sa.String(length=255), nullable=True))
        if 'refresh_expires_date' not in existing_columns:
            batch_op.add_column(sa.Column('refresh_expires_date', sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    existing_columns = {col['name'] for col in inspector.get_columns('mcp_user_tokens')}
    with op.batch_alter_table('mcp_user_tokens', schema=None) as batch_op:
        if 'oauth_client_id' in existing_columns:
            batch_op.drop_index(batch_op.f('ix_mcp_user_tokens_oauth_client_id'))
            batch_op.drop_column('oauth_client_id')
        if 'refresh_token_hash' in existing_columns:
            batch_op.drop_column('refresh_token_hash')
        if 'refresh_expires_date' in existing_columns:
            batch_op.drop_column('refresh_expires_date')

    if 'mcp_oauth_authorization_codes' in existing_tables:
        op.drop_table('mcp_oauth_authorization_codes')
    if 'mcp_oauth_clients' in existing_tables:
        op.drop_table('mcp_oauth_clients')

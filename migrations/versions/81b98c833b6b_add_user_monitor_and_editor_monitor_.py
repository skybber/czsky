"""Add User+Monitor and Editor+Monitor roles

Revision ID: 81b98c833b6b
Revises: 26896e944ee7
Create Date: 2025-10-05 15:12:46.233390

"""

from alembic import op
import sqlalchemy as sa

revision = '81b98c833b6b'
down_revision = '26896e944ee7'
branch_labels = None
depends_on = None

MONITOR = 0x20  # 32

revision = "81b98c833b6b"
down_revision = "26896e944ee7"
branch_labels = None
depends_on = None

MONITOR = 0x20  # 32


def upgrade():
    conn = op.get_bind()
    metadata = sa.MetaData()

    roles = sa.Table(
        "roles",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("index", sa.String(64)),
        sa.Column("default", sa.Boolean, nullable=False),
        sa.Column("permissions", sa.Integer, nullable=False),
        extend_existing=True,
    )

    user_row = conn.execute(
        sa.select(roles.c.index, roles.c.permissions).where(roles.c.name == "User")
    ).mappings().fetchone()

    editor_row = conn.execute(
        sa.select(roles.c.index, roles.c.permissions).where(roles.c.name == "Editor")
    ).mappings().fetchone()

    def ensure_combo(target_name: str, base_row):
        if not base_row:
            return
        exists = conn.execute(
            sa.select(roles.c.id).where(roles.c.name == target_name)
        ).first()
        if exists:
            return

        permissions = int(base_row["permissions"]) | MONITOR
        conn.execute(
            roles.insert().values(
                name=target_name,
                index=base_row["index"],
                default=False,
                permissions=permissions,
            )
        )

    ensure_combo("User+Monitor", user_row)
    ensure_combo("Editor+Monitor", editor_row)


def downgrade():
    conn = op.get_bind()
    metadata = sa.MetaData()

    roles = sa.Table(
        "roles",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        extend_existing=True,
    )

    conn.execute(
        roles.delete().where(roles.c.name.in_(["User+Monitor", "Editor+Monitor"]))
    )
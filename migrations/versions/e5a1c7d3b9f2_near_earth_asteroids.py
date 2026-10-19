"""Near-Earth asteroids: orbit type and NEO/PHA flags, close approaches

Revision ID: e5a1c7d3b9f2
Revises: b7e2d4f1a9c3
Create Date: 2026-10-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5a1c7d3b9f2'
down_revision = 'b7e2d4f1a9c3'
branch_labels = None
depends_on = None


def _parse_hex_flags(hex_flags):
    # Same rules as imports.import_minor_planets.parse_mpc_hex_flags, kept local
    # so the migration does not depend on application code.
    try:
        flags = int(str(hex_flags).strip(), 16)
    except (TypeError, ValueError):
        return None, False, False
    return (flags & 0x003F) or None, bool(flags & 0x0800), bool(flags & 0x8000)


def upgrade():
    with op.batch_alter_table('minor_planets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('orbit_type', sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column('is_neo', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('is_pha', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_index(batch_op.f('ix_minor_planets_is_neo'), ['is_neo'], unique=False)
        batch_op.create_index(batch_op.f('ix_minor_planets_is_pha'), ['is_pha'], unique=False)

    op.create_table('neo_close_approaches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('minor_planet_id', sa.Integer(), nullable=True),
    sa.Column('designation', sa.String(length=30), nullable=False),
    sa.Column('approach_time', sa.DateTime(), nullable=False),
    sa.Column('dist_au', sa.Float(), nullable=False),
    sa.Column('dist_min_au', sa.Float(), nullable=True),
    sa.Column('dist_max_au', sa.Float(), nullable=True),
    sa.Column('v_rel_kms', sa.Float(), nullable=True),
    sa.Column('h', sa.Float(), nullable=True),
    sa.Column('t_sigma', sa.String(length=16), nullable=True),
    sa.Column('orbit_id', sa.String(length=16), nullable=True),
    sa.Column('est_peak_mag', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['minor_planet_id'], ['minor_planets.id'],
                            name=op.f('fk_neo_close_approaches_minor_planet_id_minor_planets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_neo_close_approaches'))
    )
    with op.batch_alter_table('neo_close_approaches', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_neo_close_approaches_approach_time'), ['approach_time'], unique=False)
        batch_op.create_index(batch_op.f('ix_neo_close_approaches_designation'), ['designation'], unique=False)
        batch_op.create_index(batch_op.f('ix_neo_close_approaches_minor_planet_id'), ['minor_planet_id'], unique=False)

    # Fill the new flags for existing rows from hex_flags.
    conn = op.get_bind()
    minor_planets = sa.table('minor_planets',
                             sa.column('id', sa.Integer),
                             sa.column('hex_flags', sa.String),
                             sa.column('orbit_type', sa.SmallInteger),
                             sa.column('is_neo', sa.Boolean),
                             sa.column('is_pha', sa.Boolean))
    rows = conn.execute(sa.select(minor_planets.c.id, minor_planets.c.hex_flags)
                        .where(minor_planets.c.hex_flags.isnot(None))).fetchall()
    updates = []
    for row_id, hex_flags in rows:
        orbit_type, is_neo, is_pha = _parse_hex_flags(hex_flags)
        updates.append({'b_id': row_id, 'orbit_type': orbit_type, 'is_neo': is_neo, 'is_pha': is_pha})
    if updates:
        conn.execute(minor_planets.update()
                     .where(minor_planets.c.id == sa.bindparam('b_id'))
                     .values(orbit_type=sa.bindparam('orbit_type'),
                             is_neo=sa.bindparam('is_neo'),
                             is_pha=sa.bindparam('is_pha')),
                     updates)


def downgrade():
    with op.batch_alter_table('neo_close_approaches', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_neo_close_approaches_minor_planet_id'))
        batch_op.drop_index(batch_op.f('ix_neo_close_approaches_designation'))
        batch_op.drop_index(batch_op.f('ix_neo_close_approaches_approach_time'))

    op.drop_table('neo_close_approaches')

    with op.batch_alter_table('minor_planets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_minor_planets_is_pha'))
        batch_op.drop_index(batch_op.f('ix_minor_planets_is_neo'))
        batch_op.drop_column('is_pha')
        batch_op.drop_column('is_neo')
        batch_op.drop_column('orbit_type')

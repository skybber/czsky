"""Near-Earth asteroids: ephemeris segments from JPL Horizons

Revision ID: c2e8f1a4b6d3
Revises: a7c4e9b2d5f8
Create Date: 2026-10-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2e8f1a4b6d3'
down_revision = 'a7c4e9b2d5f8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('neo_ephemeris_segments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('minor_planet_id', sa.Integer(), nullable=False),
    sa.Column('start_jd', sa.Float(), nullable=False),
    sa.Column('step_minutes', sa.Float(), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('verified', sa.Boolean(), nullable=False),
    sa.Column('max_check_error_arcsec', sa.Float(), nullable=True),
    sa.Column('orbit_solution', sa.String(length=32), nullable=True),
    sa.Column('revision', sa.String(length=16), nullable=False),
    sa.Column('fetched_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['minor_planet_id'], ['minor_planets.id'],
                            name=op.f('fk_neo_ephemeris_segments_minor_planet_id_minor_planets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_neo_ephemeris_segments'))
    )
    with op.batch_alter_table('neo_ephemeris_segments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_neo_ephemeris_segments_minor_planet_id'), ['minor_planet_id'],
                              unique=False)


def downgrade():
    with op.batch_alter_table('neo_ephemeris_segments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_neo_ephemeris_segments_minor_planet_id'))

    op.drop_table('neo_ephemeris_segments')

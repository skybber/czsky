"""Minor planets

Revision ID: cd4c1022d194
Revises: 5daf63794805
Create Date: 2022-01-26 21:00:30.184914

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cd4c1022d194'
down_revision = '5daf63794805'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('minor_planet',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('magnitude_H', sa.Float(), nullable=True),
    sa.Column('magnitude_G', sa.Float(), nullable=True),
    sa.Column('epoch', sa.String(length=6), nullable=True),
    sa.Column('mean_anomaly_degrees', sa.Float(), nullable=True),
    sa.Column('argument_of_perihelion_degrees', sa.Float(), nullable=True),
    sa.Column('longitude_of_ascending_node_degrees', sa.Float(), nullable=True),
    sa.Column('inclination_degrees', sa.Float(), nullable=True),
    sa.Column('eccentricity', sa.Float(), nullable=True),
    sa.Column('mean_daily_motion_degrees', sa.Float(), nullable=True),
    sa.Column('semimajor_axis_au', sa.Float(), nullable=True),
    sa.Column('uncertainty', sa.String(length=6), nullable=True),
    sa.Column('reference', sa.String(length=10), nullable=True),
    sa.Column('observations', sa.Integer(), nullable=True),
    sa.Column('oppositions', sa.Integer(), nullable=True),
    sa.Column('observation_period', sa.String(length=9), nullable=True),
    sa.Column('rms_residual_arcseconds', sa.Float(), nullable=True),
    sa.Column('coarse_perturbers', sa.String(length=4), nullable=True),
    sa.Column('precise_perturbers', sa.String(length=4), nullable=True),
    sa.Column('computer_name', sa.String(length=11), nullable=True),
    sa.Column('hex_flags', sa.String(length=5), nullable=True),
    sa.Column('designation', sa.String(length=30), nullable=True),
    sa.Column('last_observation_date', sa.String(length=9), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_minor_planet'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('minor_planet')
    # ### end Alembic commands ###
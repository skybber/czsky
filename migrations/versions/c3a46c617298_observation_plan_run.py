"""Observation plan run

Revision ID: c3a46c617298
Revises: 1cc4ca5c52c0
Create Date: 2021-11-07 12:28:31.227921

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3a46c617298'
down_revision = '1cc4ca5c52c0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('observation_plan_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('observation_id', sa.Integer(), nullable=False),
    sa.Column('session_plan_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['observation_id'], ['observations.id'], name=op.f('fk_observation_plan_runs_observation_id_observations')),
    sa.ForeignKeyConstraint(['session_plan_id'], ['session_plans.id'], name=op.f('fk_observation_plan_runs_session_plan_id_session_plans')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_observation_plan_runs'))
    )
    op.create_table('observation_plan_run_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('observation_plan_run_id', sa.Integer(), nullable=False),
    sa.Column('dso_id', sa.Integer(), nullable=True),
    sa.Column('date_time', sa.DateTime(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['dso_id'], ['deepsky_objects.id'], name=op.f('fk_observation_plan_run_items_dso_id_deepsky_objects')),
    sa.ForeignKeyConstraint(['observation_plan_run_id'], ['observation_plan_runs.id'], name=op.f('fk_observation_plan_run_items_observation_plan_run_id_observation_plan_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_observation_plan_run_items'))
    )
    with op.batch_alter_table('observation_items', schema=None) as batch_op:
        batch_op.alter_column('observation_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('observation_items', schema=None) as batch_op:
        batch_op.alter_column('observation_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    op.drop_table('observation_plan_run_items')
    op.drop_table('observation_plan_runs')
    # ### end Alembic commands ###
"""Import history

Revision ID: c345e6d15510
Revises: 86229133e8b5
Create Date: 2022-01-09 13:13:44.236970

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c345e6d15510'
down_revision = '86229133e8b5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('import_history_recs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('import_type', sa.Enum('OBSERVATION', 'SESSION_PLAN', name='importtype'), nullable=True),
    sa.Column('status', sa.Enum('IMPORTED', 'DELETED', name='importhistoryrecstatus'), nullable=True),
    sa.Column('log', sa.Text(), nullable=True),
    sa.Column('create_by', sa.Integer(), nullable=True),
    sa.Column('create_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['create_by'], ['users.id'], name=op.f('fk_import_history_recs_create_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_history_recs'))
    )
    with op.batch_alter_table('filters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_filters_model'), ['model'], unique=False)
        batch_op.create_index(batch_op.f('ix_filters_name'), ['name'], unique=False)
        batch_op.create_index(batch_op.f('ix_filters_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_filters_vendor'), ['vendor'], unique=False)

    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('import_history_rec_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_observations_import_history_rec_id'), ['import_history_rec_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_observations_import_history_rec_id_import_history_recs'), 'import_history_recs', ['import_history_rec_id'], ['id'])

    with op.batch_alter_table('observing_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('import_history_rec_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_observing_sessions_import_history_rec_id'), ['import_history_rec_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_observing_sessions_import_history_rec_id_import_history_recs'), 'import_history_recs', ['import_history_rec_id'], ['id'])
        batch_op.drop_column('created_by_import')

    with op.batch_alter_table('session_plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('import_history_rec_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_session_plans_import_history_rec_id'), ['import_history_rec_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_session_plans_import_history_rec_id_import_history_recs'), 'import_history_recs', ['import_history_rec_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('session_plans', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_session_plans_import_history_rec_id_import_history_recs'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_session_plans_import_history_rec_id'))
        batch_op.drop_column('import_history_rec_id')

    with op.batch_alter_table('observing_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by_import', sa.BOOLEAN(), nullable=True))
        batch_op.drop_constraint(batch_op.f('fk_observing_sessions_import_history_rec_id_import_history_recs'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_observing_sessions_import_history_rec_id'))
        batch_op.drop_column('import_history_rec_id')

    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_observations_import_history_rec_id_import_history_recs'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_observations_import_history_rec_id'))
        batch_op.drop_column('import_history_rec_id')

    with op.batch_alter_table('filters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_filters_vendor'))
        batch_op.drop_index(batch_op.f('ix_filters_user_id'))
        batch_op.drop_index(batch_op.f('ix_filters_name'))
        batch_op.drop_index(batch_op.f('ix_filters_model'))

    op.drop_table('import_history_recs')
    # ### end Alembic commands ###
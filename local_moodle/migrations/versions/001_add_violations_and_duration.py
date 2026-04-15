"""add violations and test duration

Revision ID: 001
Revises: bd18b4e571c6
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa


revision = '001'
down_revision = 'bd18b4e571c6'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле test_duration в таблицу labs
    op.add_column('labs', sa.Column('test_duration', sa.Integer(), nullable=True, default=0))
    
    # Добавляем поля нарушений в таблицу attempts
    op.add_column('attempts', sa.Column('violation_tab_switch', sa.Integer(), nullable=True, default=0))
    op.add_column('attempts', sa.Column('violation_copy', sa.Boolean(), nullable=True, default=False))
    op.add_column('attempts', sa.Column('violation_fullscreen_exit', sa.Integer(), nullable=True, default=0))


def downgrade():
    op.drop_column('attempts', 'violation_fullscreen_exit')
    op.drop_column('attempts', 'violation_copy')
    op.drop_column('attempts', 'violation_tab_switch')
    op.drop_column('labs', 'test_duration')

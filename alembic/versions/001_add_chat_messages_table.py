"""add chat messages table

Revision ID: 001
Revises: 
Create Date: 2026-03-13 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建聊天消息表"""
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index('ix_cm_session_id', 'chat_messages', ['session_id'], unique=False)
    op.create_index('ix_cm_timestamp', 'chat_messages', ['timestamp'], unique=False)
    op.create_index('ix_cm_session_timestamp', 'chat_messages', ['session_id', 'timestamp'], unique=False)


def downgrade() -> None:
    """删除聊天消息表"""
    op.drop_index('ix_cm_session_timestamp', table_name='chat_messages')
    op.drop_index('ix_cm_timestamp', table_name='chat_messages')
    op.drop_index('ix_cm_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')

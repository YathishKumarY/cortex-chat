"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2025-09-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_active', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_user_id'), 'users', ['user_id'], unique=True)
    
    # Create conversations table
    op.create_table('conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_conversation_id'), 'conversations', ['conversation_id'], unique=True)
    op.create_index(op.f('ix_conversations_id'), 'conversations', ['id'], unique=False)
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)
    
    # Create chat_history table
    op.create_table('chat_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('conversation_id', sa.String(length=255), nullable=False),
        sa.Column('message_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_history_timestamp', 'chat_history', ['timestamp'], unique=False)
    op.create_index('ix_chat_history_user_conversation', 'chat_history', ['user_id', 'conversation_id'], unique=False)
    op.create_index(op.f('ix_chat_history_conversation_id'), 'chat_history', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_chat_history_id'), 'chat_history', ['id'], unique=False)
    op.create_index(op.f('ix_chat_history_user_id'), 'chat_history', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop chat_history table
    op.drop_index(op.f('ix_chat_history_user_id'), table_name='chat_history')
    op.drop_index(op.f('ix_chat_history_id'), table_name='chat_history')
    op.drop_index(op.f('ix_chat_history_conversation_id'), table_name='chat_history')
    op.drop_index('ix_chat_history_user_conversation', table_name='chat_history')
    op.drop_index('ix_chat_history_timestamp', table_name='chat_history')
    op.drop_table('chat_history')
    
    # Drop conversations table
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_conversation_id'), table_name='conversations')
    op.drop_table('conversations')
    
    # Drop users table
    op.drop_index(op.f('ix_users_user_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
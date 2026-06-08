"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        'nav_hot_paths',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('path', sa.String(500), nullable=False),
        sa.Column('label', sa.String(200), nullable=False),
        sa.Column('aliases', postgresql.ARRAY(sa.String()), server_default='{}'),
        sa.Column('hit_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_hit_at', sa.DateTime(), nullable=True),
        sa.Column('pinned', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    op.create_table(
        'nav_index',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('path', sa.String(500), nullable=False, unique=True),
        sa.Column('label', sa.String(200), nullable=False),
        sa.Column('description', sa.String(1000), server_default=''),
        sa.Column('tags', postgresql.ARRAY(sa.String()), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.execute("ALTER TABLE nav_index ADD COLUMN IF NOT EXISTS embedding vector(384)")

    op.create_table(
        'nav_query_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('raw_query', sa.String(500), nullable=False),
        sa.Column('matched_path', sa.String(500), nullable=True),
        sa.Column('layer_used', sa.String(10), nullable=False),
        sa.Column('confidence', sa.Float(), server_default='0.0'),
        sa.Column('response_ms', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    op.create_table(
        'nav_config',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_hot_paths_hit_count ON nav_hot_paths(hit_count DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hot_paths_aliases ON nav_hot_paths USING gin(aliases)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_query_log_created ON nav_query_log(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_query_log_layer ON nav_query_log(layer_used)")


def downgrade():
    op.drop_table('nav_config')
    op.drop_table('nav_query_log')
    op.drop_table('nav_index')
    op.drop_table('nav_hot_paths')

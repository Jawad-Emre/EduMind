"""add chunks.embedding vector column + pgvector extension (chain repair)

Revision ID: f0e1d2c3b4a5
Revises: a3cbaba54a80
Create Date: 2026-07-27 00:00:00.000000

This migration reconstructs a step that was applied to the live database
out-of-band but never committed as a migration: creating the pgvector
extension and the ``chunks.embedding`` vector column (plus its ivfflat
index). Without it, a *fresh* database cannot run ``alembic upgrade head``
because the next revision (58597cdc0c6f) tries to ALTER a column and DROP an
index that were never created.

It is inserted as the parent of 58597cdc0c6f. On the live DB (already stamped
at 58597cdc0c6f) it is an ancestor of the applied head, so Alembic treats it
as already applied and never runs it -> a true no-op. On a fresh DB it runs
first, so the following revision's ALTER/DROP succeed.

All statements are idempotent (IF [NOT] EXISTS) as belt-and-suspenders.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f0e1d2c3b4a5'
down_revision: Union[str, Sequence[str], None] = 'a3cbaba54a80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Original historical dimension was 768; the very next revision
    # (58597cdc0c6f) alters it down to 384. Recreate at 768 so that
    # revision's ALTER runs exactly as authored.
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding vector(768)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS chunks_embedding_idx")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS embedding")
    # Extension left in place intentionally; other objects may depend on it.

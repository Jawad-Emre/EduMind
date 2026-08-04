"""add learner memory + structured summary columns

Revision ID: a1b2c3d4e5f6
Revises: 58597cdc0c6f
Create Date: 2026-07-27 00:05:00.000000

Adds the columns backing the adaptive learner-memory + summary features:
  - subject_profiles.knowledge_state (JSON, nullable) - evolving learner profile
  - subject_profiles.pending_spike   (Float, nullable) - spike-verification carry
  - session_summaries.structured     (JSON, nullable) - topics/understood/etc.
  - session_summaries.embedding_id   -> made nullable (summaries no longer embedded)

All changes are additive or nullability-relaxing, so this is safe to apply to
the live database with existing rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '58597cdc0c6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('subject_profiles', sa.Column('knowledge_state', sa.JSON(), nullable=True))
    op.add_column('subject_profiles', sa.Column('pending_spike', sa.Float(), nullable=True))
    op.add_column('session_summaries', sa.Column('structured', sa.JSON(), nullable=True))
    op.alter_column('session_summaries', 'embedding_id',
                    existing_type=sa.String(length=255),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('session_summaries', 'embedding_id',
                    existing_type=sa.String(length=255),
                    nullable=False)
    op.drop_column('session_summaries', 'structured')
    op.drop_column('subject_profiles', 'pending_spike')
    op.drop_column('subject_profiles', 'knowledge_state')

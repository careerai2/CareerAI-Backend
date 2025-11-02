"""updated msg table

Revision ID: 1585ed76e05f
Revises: 91fd119808af
Create Date: 2025-10-30 18:53:51.126323
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1585ed76e05f'
down_revision: Union[str, Sequence[str], None] = '91fd119808af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1️⃣ Create ENUM types before using them
    message_type_enum = sa.Enum('received', 'sent', name='message_type')
    sender_enum = sa.Enum('user', 'bot', name='sender')

    bind = op.get_bind()
    message_type_enum.create(bind, checkfirst=True)
    sender_enum.create(bind, checkfirst=True)

    # 2️⃣ Add the columns
    op.add_column('chat_messages', sa.Column('text', sa.String(), nullable=True))
    op.add_column('chat_messages', sa.Column('type', message_type_enum, nullable=False))
    op.add_column('chat_messages', sa.Column('sender', sender_enum, nullable=False))

    # 3️⃣ Drop old columns if they exist
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.drop_column('message')
        batch_op.drop_column('sender_role')


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse order: remove columns first
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sender_role', postgresql.ENUM('user', 'assistant', name='sender_role'), nullable=False))
        batch_op.add_column(sa.Column('message', sa.VARCHAR(), nullable=True))
        batch_op.drop_column('sender')
        batch_op.drop_column('type')
        batch_op.drop_column('text')

    # Drop ENUM types safely
    bind = op.get_bind()
    sender_enum = sa.Enum('user', 'bot', name='sender')
    message_type_enum = sa.Enum('received', 'sent', name='message_type')

    sender_enum.drop(bind, checkfirst=True)
    message_type_enum.drop(bind, checkfirst=True)

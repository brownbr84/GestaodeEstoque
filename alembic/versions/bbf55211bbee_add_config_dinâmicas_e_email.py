"""Add config dinâmicas e email

Revision ID: bbf55211bbee
Revises: b3f01e6a8c68
Create Date: 2026-04-20 02:34:50.978739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbf55211bbee'
down_revision: Union[str, Sequence[str], None] = 'b3f01e6a8c68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('configuracoes', sa.Column('categorias_produto', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('configuracoes', sa.Column('tipos_material', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('configuracoes', sa.Column('tipos_controle', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('configuracoes', sa.Column('email_smtp', sa.String(), nullable=True))
    op.add_column('configuracoes', sa.Column('senha_smtp', sa.String(), nullable=True))
    op.add_column('configuracoes', sa.Column('emails_destinatarios', sa.JSON(), nullable=True, server_default='[]'))

def downgrade() -> None:
    op.drop_column('configuracoes', 'categorias_produto')
    op.drop_column('configuracoes', 'tipos_material')
    op.drop_column('configuracoes', 'tipos_controle')
    op.drop_column('configuracoes', 'email_smtp')
    op.drop_column('configuracoes', 'senha_smtp')
    op.drop_column('configuracoes', 'emails_destinatarios')

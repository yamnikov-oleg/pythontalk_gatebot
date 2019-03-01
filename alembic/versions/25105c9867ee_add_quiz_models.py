"""Add quiz models

Revision ID: 25105c9867ee
Revises:
Create Date: 2019-03-01 17:52:40.738114

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25105c9867ee'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'quizpass',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_quizpass_user_id'), 'quizpass', ['user_id'], unique=False)
    op.create_table(
        'quizitem',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quizpass_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('correct_answer', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['quizpass_id'], ['quizpass.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'option',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quizitem_id', sa.Integer(), nullable=False),
        sa.Column('index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['quizitem_id'], ['quizitem.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('option')
    op.drop_table('quizitem')
    op.drop_index(op.f('ix_quizpass_user_id'), table_name='quizpass')
    op.drop_table('quizpass')

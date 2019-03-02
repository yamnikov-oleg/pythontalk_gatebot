"""Add some quiz columns

Revision ID: a8927d96dfd6
Revises: 25105c9867ee
Create Date: 2019-03-02 22:36:38.615168

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8927d96dfd6'
down_revision = '25105c9867ee'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('quizitem', sa.Column('index', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('quizitem', sa.Column('index', sa.Integer(), nullable=False))
    op.add_column('quizpass', sa.Column('correct_required', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('quizpass', sa.Column('correct_required', sa.Integer(), nullable=False))


def downgrade():
    op.drop_column('quizpass', 'correct_required')
    op.drop_column('quizitem', 'index')

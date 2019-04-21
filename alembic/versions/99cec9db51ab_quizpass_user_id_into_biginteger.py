"""QuizPass.user_id into BigInteger

Revision ID: 99cec9db51ab
Revises: d4837fdeb45c
Create Date: 2019-04-21 19:54:51.308419

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '99cec9db51ab'
down_revision = 'd4837fdeb45c'
branch_labels = None
depends_on = None


def is_sqlite():
    from alembic.ddl.sqlite import SQLiteImpl
    return isinstance(op.get_context().impl, SQLiteImpl)


def upgrade():
    if not is_sqlite():
        op.alter_column('quizpass', 'user_id', type_=sa.BigInteger(), existing_type=sa.Integer())


def downgrade():
    if not is_sqlite():
        op.alter_column('quizpass', 'user_id', type_=sa.Integer(), existing_type=sa.BigInteger())

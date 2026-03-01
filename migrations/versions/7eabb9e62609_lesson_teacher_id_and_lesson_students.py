"""add active to students and teachers

Revision ID: 7eabb9e62609
Revises: 
Create Date: 2026-03-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7eabb9e62609'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('active', sa.Boolean(), nullable=False, server_default='true'))

    with op.batch_alter_table('teachers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('active', sa.Boolean(), nullable=False, server_default='true'))


def downgrade():
    with op.batch_alter_table('teachers', schema=None) as batch_op:
        batch_op.drop_column('active')

    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('active')

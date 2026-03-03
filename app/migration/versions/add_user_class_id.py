"""add class_id to users and secretary role

Revision ID: a1b2c3d4e5f6
Revises: 7eabb9e62609
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '7eabb9e62609'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('class_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_users_class_id', 'classes',
            ['class_id'], ['id'],
            ondelete='SET NULL'
        )

def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_class_id', type_='foreignkey')
        batch_op.drop_column('class_id')

"""Add performance indexes for operational queries

Revision ID: 6f7f0e3e6a42
Revises: 30b49dce8990
Create Date: 2026-02-19 15:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6f7f0e3e6a42"
down_revision = "30b49dce8990"
branch_labels = None
depends_on = None


INDEX_DEFINITIONS = [
    ("ix_rawmaterialreceptions_date", "rawmaterialreceptions", ["date"]),
    ("ix_lots_rawmaterialreception_id", "lots", ["rawmaterialreception_id"]),
    ("ix_lots_variety_id", "lots", ["variety_id"]),
    ("ix_lots_rawmaterialpackaging_id", "lots", ["rawmaterialpackaging_id"]),
    ("ix_fulltruckweights_lot_id", "fulltruckweights", ["lot_id"]),
    ("ix_lotsqc_date", "lotsqc", ["date"]),
    ("ix_samplesqc_date", "samplesqc", ["date"]),
    ("ix_area_user_user_id", "area_user", ["user_id"]),
    ("ix_role_user_user_id", "role_user", ["user_id"]),
    ("ix_client_user_user_id", "client_user", ["user_id"]),
    ("ix_rawmaterialreception_client_client_id", "rawmaterialreception_client", ["client_id"]),
    ("ix_rawmaterialreception_grower_grower_id", "rawmaterialreception_grower", ["grower_id"]),
    ("ix_fumigation_lot_lot_id", "fumigation_lot", ["lot_id"]),
]


def _existing_indexes(bind, table_name):
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()
    for index_name, table_name, columns in INDEX_DEFINITIONS:
        if index_name not in _existing_indexes(bind, table_name):
            op.create_index(index_name, table_name, columns, unique=False)


def downgrade():
    bind = op.get_bind()
    existing = {
        table_name: _existing_indexes(bind, table_name)
        for _index_name, table_name, _columns in INDEX_DEFINITIONS
    }
    for index_name, table_name, _columns in INDEX_DEFINITIONS:
        if index_name in existing.get(table_name, set()):
            op.drop_index(index_name, table_name=table_name)

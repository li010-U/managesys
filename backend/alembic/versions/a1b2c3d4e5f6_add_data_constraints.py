"""Add DB-level constraints for data consistency.

Migration ID: enforce unique rack codes / grid positions, device U-start
uniqueness.  Uses SQLite batch mode (copy-and-move) for constraint changes.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "5c9d0be78b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) racks.code globally unique (replace old non-unique index)
    op.drop_index("ix_racks_code", table_name="racks")
    with op.batch_alter_table("racks") as batch_op:
        batch_op.create_unique_constraint("uq_racks_code", ["code"])

    # 2) no two racks in same room share a grid cell (row, col)
    with op.batch_alter_table("racks") as batch_op:
        batch_op.create_unique_constraint("uq_racks_room_row_col", ["room_id", "row_pos", "col_pos"])

    # 3) no two devices start at the same U in the same rack
    with op.batch_alter_table("devices") as batch_op:
        batch_op.create_unique_constraint("uq_devices_rack_start_u", ["rack_id", "start_u"])


def downgrade() -> None:
    with op.batch_alter_table("devices") as batch_op:
        batch_op.drop_constraint("uq_devices_rack_start_u", type_="unique")
    with op.batch_alter_table("racks") as batch_op:
        batch_op.drop_constraint("uq_racks_room_row_col", type_="unique")
        batch_op.drop_constraint("uq_racks_code", type_="unique")
    op.create_index("ix_racks_code", "racks", ["code"])

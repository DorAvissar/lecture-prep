"""rename onedrive_folder to drive_folder

Revision ID: 10066b88b6b1
Revises: 1d792191bd5a
Create Date: 2026-10-28 23:30:53.590167

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "10066b88b6b1"
down_revision: str | Sequence[str] | None = "1d792191bd5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Hand-edited: autogenerate cannot tell a rename from "drop one column, add another", and its draft
# (add drive_folder, drop onedrive_folder) would lose existing data. A rename keeps it.


def upgrade() -> None:
    op.alter_column("courses", "onedrive_folder", new_column_name="drive_folder")


def downgrade() -> None:
    op.alter_column("courses", "drive_folder", new_column_name="onedrive_folder")

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = ("feature", "observation", "forecast", "alert", "historical_event", "comuna_index", "municipal_asset", "municipal_incident")
BASE = "'official','observed','forecast','official_warning','historical','municipal','derived'"
EXTENDED = BASE + ",'estimated','modelled'"


def _replace(classes: str) -> None:
    for table in TABLES:
        op.execute(f"alter table {table} drop constraint {table}_data_class_check")
        op.execute(f"alter table {table} add constraint {table}_data_class_check check (data_class in ({classes}))")


def upgrade() -> None:
    _replace(EXTENDED)


def downgrade() -> None:
    _replace(BASE)

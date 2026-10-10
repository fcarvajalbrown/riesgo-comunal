from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TABLES = ("feature", "observation", "forecast", "alert", "historical_event", "comuna_index", "municipal_asset", "municipal_incident")
PREVIOUS = "'official','observed','forecast','official_warning','historical','municipal','derived','estimated','modelled'"
EXTENDED = PREVIOUS + ",'international'"


def _replace(classes: str) -> None:
    for table in TABLES:
        op.execute(f"alter table {table} drop constraint {table}_data_class_check")
        op.execute(f"alter table {table} add constraint {table}_data_class_check check (data_class in ({classes}))")


def upgrade() -> None:
    _replace(EXTENDED)
    op.execute("update alert set data_class = 'international' where source_key in ('gdacs', 'ptwc_tsunami')")


def downgrade() -> None:
    op.execute("update alert set data_class = 'official_warning' where data_class = 'international'")
    _replace(PREVIOUS)

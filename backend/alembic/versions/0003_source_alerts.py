from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table alert add column external_id text")
    op.execute("alter table alert add column properties jsonb not null default '{}'::jsonb")
    op.execute("create unique index alert_source_external_idx on alert (source_key, external_id) where external_id is not null")
    op.execute("create index alert_area_idx on alert using gist (area)")


def downgrade() -> None:
    op.execute("drop index alert_area_idx")
    op.execute("drop index alert_source_external_idx")
    op.execute("alter table alert drop column properties")
    op.execute("alter table alert drop column external_id")

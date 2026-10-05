from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table upload drop constraint upload_kind_check")
    op.execute("alter table upload add constraint upload_kind_check check (kind in ('assets','incidents','sectors','document','raster'))")
    op.execute(
        """
        create table municipal_raster (
            id bigserial primary key,
            municipality_id int not null references municipality(id) on delete cascade,
            name text not null,
            preview_path text not null,
            footprint geometry(Polygon, 4326) not null,
            properties jsonb not null default '{}'::jsonb,
            is_demo boolean not null default false,
            data_class text not null default 'municipal',
            upload_id bigint references upload(id) on delete cascade,
            provenance_id bigint references provenance(id) on delete set null,
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index municipal_raster_footprint_gix on municipal_raster using gist (footprint)")
    op.execute("create index municipal_raster_municipality_idx on municipal_raster (municipality_id)")


def downgrade() -> None:
    op.execute("drop table municipal_raster")
    op.execute("delete from upload where kind = 'raster'")
    op.execute("alter table upload drop constraint upload_kind_check")
    op.execute("alter table upload add constraint upload_kind_check check (kind in ('assets','incidents','sectors','document'))")

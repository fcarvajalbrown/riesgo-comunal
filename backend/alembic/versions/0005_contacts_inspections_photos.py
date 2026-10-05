from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

KINDS = "'assets','incidents','sectors','document','raster','contacts','inspections','photo'"
PREVIOUS = "'assets','incidents','sectors','document','raster'"


def upgrade() -> None:
    op.execute("alter table upload drop constraint upload_kind_check")
    op.execute(f"alter table upload add constraint upload_kind_check check (kind in ({KINDS}))")
    op.execute(
        """
        create table emergency_contact (
            id bigserial primary key,
            municipality_id int not null references municipality(id) on delete cascade,
            kind text not null check (kind in ('contacto','personal')),
            name text not null,
            role text,
            organization text,
            phone text,
            email text,
            notes text,
            is_demo boolean not null default false,
            upload_id bigint references upload(id) on delete cascade,
            provenance_id bigint references provenance(id) on delete set null
        )
        """
    )
    op.execute("create index emergency_contact_municipality_idx on emergency_contact (municipality_id, kind)")
    op.execute(
        """
        create table inspection (
            id bigserial primary key,
            municipality_id int not null references municipality(id) on delete cascade,
            asset_id bigint references municipal_asset(id) on delete set null,
            asset_name text not null,
            inspected_on date not null,
            status text,
            notes text,
            inspector text,
            is_demo boolean not null default false,
            upload_id bigint references upload(id) on delete cascade,
            provenance_id bigint references provenance(id) on delete set null
        )
        """
    )
    op.execute("create index inspection_municipality_idx on inspection (municipality_id, inspected_on desc)")
    op.execute("create index inspection_asset_idx on inspection (asset_id)")
    op.execute(
        """
        create table photo (
            id bigserial primary key,
            municipality_id int not null references municipality(id) on delete cascade,
            asset_id bigint references municipal_asset(id) on delete set null,
            caption text,
            content_type text not null,
            stored_path text not null,
            is_demo boolean not null default false,
            upload_id bigint references upload(id) on delete cascade,
            provenance_id bigint references provenance(id) on delete set null,
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index photo_asset_idx on photo (municipality_id, asset_id)")


def downgrade() -> None:
    op.execute("drop table photo")
    op.execute("drop table inspection")
    op.execute("drop table emergency_contact")
    op.execute("delete from upload where kind in ('contacts','inspections','photo')")
    op.execute("alter table upload drop constraint upload_kind_check")
    op.execute(f"alter table upload add constraint upload_kind_check check (kind in ({PREVIOUS}))")

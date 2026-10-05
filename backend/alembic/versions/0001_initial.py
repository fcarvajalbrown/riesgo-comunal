from alembic import op
from sqlalchemy import text

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ROLES = "'SUPER_ADMIN','MUNICIPAL_ADMIN','ALCALDE','EMERGENCIAS','SECPLAN','COMUNICACIONES','VIEWER'"
DATA_CLASSES = "'official','observed','forecast','official_warning','historical','municipal','derived'"

SCHEMA = f"""
create extension if not exists postgis;

create table municipality (
    id serial primary key,
    cut_code text not null unique,
    name text not null,
    region text,
    slug text not null unique,
    boundary geometry(MultiPolygon, 4326),
    config jsonb not null default '{{}}'::jsonb,
    created_at timestamptz not null default now()
);
create index municipality_boundary_gix on municipality using gist (boundary);

create table app_user (
    id serial primary key,
    municipality_id int references municipality(id) on delete cascade,
    email text not null unique,
    name text not null,
    password_hash text not null,
    role text not null check (role in ({ROLES})),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    check (role = 'SUPER_ADMIN' or municipality_id is not null)
);

create table audit_log (
    id bigserial primary key,
    user_id int references app_user(id) on delete set null,
    municipality_id int references municipality(id) on delete cascade,
    action text not null,
    target text,
    details jsonb not null default '{{}}'::jsonb,
    at timestamptz not null default now()
);
create index audit_log_municipality_idx on audit_log (municipality_id, at desc);

create table source (
    key text primary key,
    name text not null,
    organization text not null,
    url text not null,
    license text not null,
    commercial_use text not null,
    cache_allowed text not null,
    authority text not null,
    attribution text not null,
    interval_minutes int not null,
    enabled boolean not null default true,
    requires text[] not null default '{{}}',
    last_attempt_at timestamptz,
    last_success_at timestamptz,
    last_error text,
    last_record_count int
);

create table ingestion_job (
    id bigserial primary key,
    source_key text not null references source(key) on delete cascade,
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    status text not null default 'running' check (status in ('running','success','failed')),
    record_count int not null default 0,
    warnings jsonb not null default '[]'::jsonb,
    error text
);
create index ingestion_job_source_idx on ingestion_job (source_key, started_at desc);

create table upload (
    id bigserial primary key,
    municipality_id int not null references municipality(id) on delete cascade,
    filename text not null,
    kind text not null check (kind in ('assets','incidents','sectors','document')),
    category text,
    content_type text,
    size_bytes bigint not null,
    sha256 text not null,
    stored_path text not null,
    status text not null default 'processing' check (status in ('processing','done','failed')),
    record_count int not null default 0,
    error text,
    is_demo boolean not null default false,
    uploaded_by int references app_user(id) on delete set null,
    uploaded_at timestamptz not null default now()
);
create index upload_municipality_idx on upload (municipality_id, uploaded_at desc);

create table provenance (
    id bigserial primary key,
    source_key text references source(key) on delete cascade,
    municipality_id int references municipality(id) on delete cascade,
    upload_id bigint references upload(id) on delete cascade,
    dataset text not null,
    url text,
    source_time timestamptz,
    acquired_at timestamptz not null default now(),
    ingested_at timestamptz not null default now(),
    ingestion_job_id bigint references ingestion_job(id) on delete set null,
    transformation text,
    version text,
    check (source_key is not null or upload_id is not null)
);
create index provenance_source_idx on provenance (source_key, dataset, ingested_at desc);

create table feature (
    id bigserial primary key,
    source_key text not null references source(key) on delete cascade,
    dataset text not null,
    external_id text not null,
    name text,
    category text,
    cut_code text,
    properties jsonb not null default '{{}}'::jsonb,
    geom geometry(Geometry, 4326) not null,
    data_class text not null default 'official' check (data_class in ({DATA_CLASSES})),
    source_updated_at timestamptz,
    provenance_id bigint references provenance(id) on delete set null,
    unique (source_key, dataset, external_id)
);
create index feature_geom_gix on feature using gist (geom);
create index feature_dataset_idx on feature (dataset, cut_code);

create table observation (
    id bigserial primary key,
    source_key text not null references source(key) on delete cascade,
    station_external_id text not null,
    station_name text,
    parameter text not null,
    parameter_name text,
    value double precision,
    unit text,
    observed_at timestamptz not null,
    validation_status text not null default 'unknown',
    geom geometry(Point, 4326),
    cut_code text,
    data_class text not null default 'observed' check (data_class in ({DATA_CLASSES})),
    provenance_id bigint references provenance(id) on delete set null,
    unique (source_key, station_external_id, parameter, observed_at)
);
create index observation_geom_gix on observation using gist (geom);
create index observation_lookup_idx on observation (parameter, observed_at desc);

create table forecast (
    id bigserial primary key,
    source_key text not null references source(key) on delete cascade,
    location_external_id text,
    parameter text not null,
    value double precision,
    unit text,
    valid_from timestamptz not null,
    valid_to timestamptz,
    issued_at timestamptz,
    geom geometry(Geometry, 4326),
    cut_code text,
    data_class text not null default 'forecast' check (data_class in ({DATA_CLASSES})),
    provenance_id bigint references provenance(id) on delete set null
);
create index forecast_geom_gix on forecast using gist (geom);

create table alert (
    id bigserial primary key,
    municipality_id int references municipality(id) on delete cascade,
    source_key text references source(key) on delete set null,
    issuer text not null,
    hazard text not null,
    level text not null,
    title text not null,
    description text,
    source_url text not null,
    starts_at timestamptz not null,
    ends_at timestamptz,
    area geometry(MultiPolygon, 4326),
    data_class text not null default 'official_warning' check (data_class in ({DATA_CLASSES})),
    entered_by int references app_user(id) on delete set null,
    created_at timestamptz not null default now(),
    provenance_id bigint references provenance(id) on delete set null
);
create index alert_municipality_idx on alert (municipality_id, starts_at desc);

create table historical_event (
    id bigserial primary key,
    source_key text not null references source(key) on delete cascade,
    dataset text not null,
    external_id text not null,
    hazard text not null,
    occurred_at timestamptz not null,
    magnitude double precision,
    depth_km double precision,
    place text,
    properties jsonb not null default '{{}}'::jsonb,
    geom geometry(Point, 4326) not null,
    data_class text not null default 'historical' check (data_class in ({DATA_CLASSES})),
    provenance_id bigint references provenance(id) on delete set null,
    unique (source_key, external_id)
);
create index historical_event_geom_gix on historical_event using gist (geom);
create index historical_event_time_idx on historical_event (hazard, occurred_at desc);

create table comuna_index (
    id bigserial primary key,
    source_key text not null references source(key) on delete cascade,
    index_key text not null,
    cut_code text not null,
    year int,
    value double precision,
    level text,
    components jsonb not null default '{{}}'::jsonb,
    data_class text not null default 'official' check (data_class in ({DATA_CLASSES})),
    provenance_id bigint references provenance(id) on delete set null,
    unique (source_key, index_key, cut_code, year)
);

create table sector (
    id bigserial primary key,
    municipality_id int not null references municipality(id) on delete cascade,
    name text not null,
    kind text not null check (kind in ('municipal','analysis_cell')),
    geom geometry(MultiPolygon, 4326) not null,
    is_demo boolean not null default false,
    upload_id bigint references upload(id) on delete cascade,
    provenance_id bigint references provenance(id) on delete set null
);
create index sector_geom_gix on sector using gist (geom);
create index sector_municipality_idx on sector (municipality_id, kind);

create table municipal_asset (
    id bigserial primary key,
    municipality_id int not null references municipality(id) on delete cascade,
    category text not null,
    name text not null,
    properties jsonb not null default '{{}}'::jsonb,
    geom geometry(Geometry, 4326) not null,
    is_demo boolean not null default false,
    data_class text not null default 'municipal' check (data_class in ({DATA_CLASSES})),
    upload_id bigint references upload(id) on delete cascade,
    provenance_id bigint references provenance(id) on delete set null
);
create index municipal_asset_geom_gix on municipal_asset using gist (geom);
create index municipal_asset_municipality_idx on municipal_asset (municipality_id, category);

create table municipal_incident (
    id bigserial primary key,
    municipality_id int not null references municipality(id) on delete cascade,
    hazard text not null,
    occurred_on date not null,
    sector_name text,
    description text,
    affected_people int,
    geom geometry(Point, 4326),
    is_demo boolean not null default false,
    data_class text not null default 'municipal' check (data_class in ({DATA_CLASSES})),
    upload_id bigint references upload(id) on delete cascade,
    provenance_id bigint references provenance(id) on delete set null
);
create index municipal_incident_geom_gix on municipal_incident using gist (geom);
create index municipal_incident_municipality_idx on municipal_incident (municipality_id, hazard, occurred_on);

create table document (
    id bigserial primary key,
    municipality_id int not null references municipality(id) on delete cascade,
    upload_id bigint references upload(id) on delete cascade,
    title text not null,
    filename text not null,
    page_count int not null default 0,
    is_demo boolean not null default false,
    created_at timestamptz not null default now()
);

create table document_chunk (
    id bigserial primary key,
    document_id bigint not null references document(id) on delete cascade,
    municipality_id int not null references municipality(id) on delete cascade,
    chunk_index int not null,
    page int,
    content text not null,
    tsv tsvector generated always as (to_tsvector('spanish', content)) stored
);
create index document_chunk_tsv_gix on document_chunk using gin (tsv);
create index document_chunk_municipality_idx on document_chunk (municipality_id);
"""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(SCHEMA))
    available = conn.execute(text("select 1 from pg_available_extensions where name = 'vector'")).scalar()
    if available:
        conn.execute(text("create extension if not exists vector"))
        conn.execute(text("alter table document_chunk add column embedding vector"))


def downgrade() -> None:
    op.get_bind().execute(
        text(
            """
            drop table if exists document_chunk, document, municipal_incident, municipal_asset, sector,
                comuna_index, historical_event, alert, forecast, observation, feature, provenance, upload,
                ingestion_job, source, audit_log, app_user, municipality cascade
            """
        )
    )

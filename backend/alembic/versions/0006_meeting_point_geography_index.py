from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create index if not exists feature_meeting_point_geog_gix on feature using gist ((geom::geography)) "
        "where dataset = 'tsunami_meeting_point'"
    )


def downgrade() -> None:
    op.execute("drop index if exists feature_meeting_point_geog_gix")

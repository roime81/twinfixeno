"""Initial schema baseline.

This first baseline deliberately uses SQLAlchemy metadata so it can adopt an
existing MVP database whose tables were previously created at application
startup. Future schema changes must use explicit, reviewed Alembic operations.
"""
from alembic import op
from app.database import Base
from app import models  # noqa: F401 - register metadata

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)

    if bind.dialect.name == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION twinfixeno_reject_snapshot_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Twin snapshots are append-only; create a new version';
        END;
        $$ LANGUAGE plpgsql;
        """)
        op.execute("""
        CREATE OR REPLACE FUNCTION twinfixeno_reject_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Audit events are append-only';
        END;
        $$ LANGUAGE plpgsql;
        """)
        for table in ("twin_snapshots", "twin_snapshot_artifacts"):
            trigger = f"trg_{table}_immutable"
            op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
            op.execute(
                f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION twinfixeno_reject_snapshot_mutation()"
            )
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events")
        op.execute(
            "CREATE TRIGGER trg_audit_events_immutable BEFORE UPDATE OR DELETE "
            "ON audit_events FOR EACH ROW EXECUTE FUNCTION twinfixeno_reject_audit_mutation()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("twin_snapshots", "twin_snapshot_artifacts"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS twinfixeno_reject_snapshot_mutation()")
        op.execute("DROP FUNCTION IF EXISTS twinfixeno_reject_audit_mutation()")
    Base.metadata.drop_all(bind=bind, checkfirst=True)

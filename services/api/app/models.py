from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, JSON, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    given_name: Mapped[str] = mapped_column(String(100))
    family_name: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(32), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    observations: Mapped[list["Observation"]] = relationship(back_populates="patient", cascade="all, delete-orphan")

class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    display: Mapped[str] = mapped_column(String(120))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(24))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    patient: Mapped[Patient] = relationship(back_populates="observations")

class TwinSnapshot(Base):
    __tablename__ = "twin_snapshots"
    __table_args__ = (UniqueConstraint("patient_id", "version", name="uq_snapshot_patient_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PatientAccessGrant(Base):
    __tablename__ = "patient_access_grants"
    __table_args__ = (UniqueConstraint("patient_id", "user_subject", "username", name="uq_patient_access_principal"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    user_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_level: Mapped[str] = mapped_column(String(16), default="read")

class FhirClinicalResource(Base):
    __tablename__ = "fhir_clinical_resources"
    __table_args__ = (UniqueConstraint("resource_type", "fhir_id", name="uq_fhir_resource_type_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    resource_type: Mapped[str] = mapped_column(String(32), index=True)
    fhir_id: Mapped[str] = mapped_column(String(128))
    version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_system: Mapped[str] = mapped_column(String(128), default="hapi-fhir")
    content_sha256: Mapped[str] = mapped_column(String(64))
    resource_json: Mapped[dict] = mapped_column(JSON)

class TwinSnapshotArtifact(Base):
    __tablename__ = "twin_snapshot_artifacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("twin_snapshots.id", ondelete="RESTRICT"), unique=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    provenance: Mapped[dict] = mapped_column(JSON)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

def _immutable_artifact(mapper, connection, target):
    raise ValueError("Twin snapshot artifacts are immutable; create a new snapshot instead")

event.listen(TwinSnapshotArtifact, "before_update", _immutable_artifact)
event.listen(TwinSnapshotArtifact, "before_delete", _immutable_artifact)

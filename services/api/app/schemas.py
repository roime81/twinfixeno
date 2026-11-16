from datetime import date, datetime
from pydantic import BaseModel, ConfigDict

class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_id: str
    given_name: str
    family_name: str
    birth_date: date
    sex: str

class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    display: str
    value: float
    unit: str
    observed_at: datetime

class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    version: int
    summary: str
    created_at: datetime

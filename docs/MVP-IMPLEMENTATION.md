# MVP implementation status

## Implemented
- Next.js 15 / React 19 dashboard with Keycloak browser login using authorization-code flow and PKCE.
- Keycloak development realm with demo clinician, administrator and researcher identities.
- FastAPI RS256 JWT signature, issuer and audience validation against Keycloak JWKS.
- Patient-level access grants bound to Keycloak subject and/or username.
- Role policy: administrator has platform-wide access; clinicians can read/write assigned patients; researchers have read-only access to assigned patients.
- Administrator-only access-grant create/update and revoke endpoints.
- HAPI FHIR R4 Patient synchronisation.
- FHIR R4 ingestion of Observation, Condition and Encounter resources, with patient-reference verification, pagination, version metadata and content hashes.
- Persisted FHIR resource records and a chronological clinical timeline API and dashboard section.
- Immutable, versioned twin snapshots with canonical JSON SHA-256 digest and source-level provenance.
- PostgreSQL triggers reject UPDATE/DELETE against snapshot headers and snapshot artifacts; ORM hooks enforce append-only behavior in tests and SQLite development.
- Pytest API integration tests for access control, FHIR ingestion, timeline, snapshot integrity and immutability.
- GitHub Actions workflow runs API tests for pushes and pull requests.

## Patient access policy
| Role | Patient scope | Read | Write |
|---|---|---:|---:|
| `twinfixeno-admin` | All patients | Yes | Yes |
| `clinician` | Explicit patient grant | Yes | Yes, only with write grant |
| `researcher` | Explicit patient grant | Yes | No |
| Other / no role | None | No | No |

A patient without a matching subject or username grant is returned as not found to reduce patient enumeration. Administrators manage grants through:
- `POST /api/v1/patients/{id}/access-grants`
- `DELETE /api/v1/patients/{id}/access-grants/{grant_id}`

## Demo identities
All credentials below are temporary development-only credentials. Keycloak forces password change on first login. Change them before sharing the environment and never expose the development realm publicly.
- Clinician: `demo.clinician` / `Demo-Only-Change-Me-2026!` (write grant to SYN-0001)
- Researcher: `demo.researcher` / `Demo-Research-Change-Me-2026!` (read-only grant to SYN-0001)
- Administrator: `demo.admin` / `Demo-Admin-Change-Me-2026!` (platform-wide access and grant management)

## FHIR endpoints
- HAPI FHIR base URL inside Compose: `http://fhir:8080/fhir`
- Host capability statement: http://localhost:8090/fhir/metadata
- Synchronise Patient and ingest supported clinical resources: `POST /api/v1/patients/{id}/fhir/sync`
- Search matching FHIR Patient: `GET /api/v1/patients/{id}/fhir`
- FHIR-backed timeline: `GET /api/v1/patients/{id}/timeline`

The ingestion adapter requests Observation, Condition and Encounter resources scoped to the resolved FHIR Patient reference. It verifies each returned resource's subject/patient reference before persistence. Updates are upserted by FHIR resource type and logical id; the FHIR meta.versionId, meta.lastUpdated, status, effective date, full resource JSON and SHA-256 are retained. Pagination is followed only when the next link remains on the configured FHIR server origin and path.

## Immutable snapshots and provenance
A snapshot consists of an append-only snapshot header and a one-to-one artifact containing:
- Canonical JSON payload of local observations and imported FHIR resources.
- SHA-256 digest of the canonical payload.
- Capture timestamp and creator.
- Per-source provenance including source system, resource type, source id, FHIR version id / lastUpdated where applicable, observation timestamp, and per-record content hash.

The API exposes:
- `POST /api/v1/patients/{id}/snapshots`
- `GET /api/v1/patients/{id}/snapshots`
- `GET /api/v1/patients/{id}/snapshots/{snapshot_id}`

Snapshots are never edited in place. Create a new version to capture changed source data. PostgreSQL triggers enforce append-only records at the database layer; SQLAlchemy hooks provide the same protection in local SQLite/test use. The digest provides integrity evidence, not a digital signature or proof of trusted origin.

## Automated tests
Run locally:
```bash
cd services/api
python -m pip install -r requirements.txt
DATABASE_URL=sqlite:///./test.db AUTH_REQUIRED=false pytest -q
```
On Windows PowerShell:
```powershell
cd services/api
python -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///./test.db"
$env:AUTH_REQUIRED = "false"
pytest -q
```
GitHub Actions runs the same API test suite on pushes to main and pull requests.

## Limitations and production hardening
- This remains a synthetic-data MVP, not a clinical system or medical device.
- The development Keycloak realm, demo users and passwords are not production identity configuration.
- Fine-grained policies are patient-grant based; organisational tenancy, care-team relationships, purpose-of-use, consent, break-glass access, audit events and delegated access still need design.
- FHIR adapter currently ingests Observation, Condition and Encounter. It does not yet ingest MedicationRequest, DiagnosticReport, Procedure, AllergyIntolerance or Provenance.
- FHIR resources are queried by patient reference; production deployment should use a secured FHIR endpoint, TLS, service identity, terminology validation and robust retry/backoff.
- Snapshot SHA-256 is an integrity checksum. Add signing, key custody and independent audit storage for tamper-evident regulated workflows.
- HAPI FHIR persistence, backup/restore, migrations, retention and high availability require production configuration.
- The GitHub Actions workflow is committed, but its first hosted run must complete before claiming a green CI result.

The demo patient is fictional. Never use real patient data in this repository or its development environment.

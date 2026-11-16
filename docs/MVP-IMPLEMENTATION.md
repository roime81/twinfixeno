# MVP implementation status

## Integrated local release

The repository now runs as one Docker Compose application stack:

- Next.js 15 / React 19 web application.
- FastAPI application API.
- PostgreSQL 16 application database.
- Keycloak 26 OIDC identity service with browser PKCE.
- HAPI FHIR R4 server.
- Apache APISIX API gateway.

Start the synthetic-data environment from the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config
docker compose up --build -d
docker compose ps
```

The supported local URLs are:

| Component | URL |
|---|---|
| Web application | http://localhost:3000 |
| FastAPI OpenAPI | http://localhost:8000/docs |
| APISIX gateway | http://localhost:9080 |
| Keycloak | http://localhost:8081 |
| HAPI FHIR metadata | http://localhost:8090/fhir/metadata |

Compose includes restart policies, persistent PostgreSQL and Keycloak volumes, database health checks, and one-shot curl readiness gates for Keycloak and HAPI FHIR before the API starts. The web workspace waits for the API health check. All host ports bind to `127.0.0.1` for local-only access. The API has `/health` and database-backed `/health/ready` endpoints. Browser-visible API and Keycloak URLs are loaded at runtime from `/runtime-config`, not embedded at image build time.

## Implemented application capabilities

### Identity and access
- Keycloak browser login using authorization-code flow and PKCE.
- FastAPI RS256 JWT verification, issuer/audience validation and Keycloak JWKS.
- Role policy: administrators have platform-wide access; clinicians and researchers require explicit patient grants.
- Clinicians can write only when a patient grant is `write`; researchers are read-only.
- UI controls now use the server-side patient permission endpoint rather than the realm role alone.
- Administrator-only grant list, create/update and revoke workflows.

### Patient registry
- List authorised patients.
- Search by synthetic ID, given name or family name.
- Administrator-only creation of synthetic patients.
- Patient selection drives the rest of the workspace.
- Only synthetic IDs matching the `SYN-` prefix are accepted by the create API.

### FHIR R4 integration
- Patient upsert/search in HAPI FHIR.
- Local synthetic observations are idempotently published as FHIR Observation resources before import.
- Observation, Condition and Encounter resources are imported using patient-scoped FHIR searches.
- Patient-reference checks, pagination origin validation, version metadata and resource hashes are retained.
- Clinical timeline displays imported resources and source identity.
- HAPI FHIR remains a development service. Profiles, terminology, authentication, persistence and operational controls require production work.

### Twin engine and snapshots
- Snapshot headers and artifacts are versioned and append-only.
- Canonical JSON payload and SHA-256 integrity checksum.
- Source provenance includes local observation IDs and FHIR resource type/id/version/lastUpdated/content hash.
- Snapshot history and artifact inspection are available in the UI.
- The UI re-computes the checksum verification status through the API.

### Simulation studio
- Scenario runs are persisted in PostgreSQL.
- A scenario selects a recorded baseline observation and applies a bounded percentage delta.
- The run stores the baseline reference, inputs, formula identifier/version, result, assumptions, timestamp and creator.
- All results are prominently labelled **Hypothetical scenario — not a clinical prediction**.
- This is an arithmetic scenario tool, not a validated physiological or disease-progression model.

### Evidence assistant
- A local deterministic context report summarises available observations and imported FHIR resource counts/ranges.
- The report states the engine identifier and limitations.
- No patient data is sent to an external model provider.
- This feature is not an LLM, RAG pipeline or clinical decision-support system. The private LLM/RAG milestone remains outstanding.

### Governance and audit
- Audit events are recorded for snapshot creation and inspection, patient observation/timeline/context access, patient creation, simulations, FHIR sync and grant changes.
- Audit rows are append-only in application ORM hooks and PostgreSQL triggers.
- Administrators can review recent audit events in the UI.
- This is an application-level audit foundation, not yet an independently protected regulatory audit service or distributed trace platform.

## API routes

All `/api/v1` routes require a valid Keycloak bearer token by default.

| Route | Purpose |
|---|---|
| `GET /api/v1/me` | Current user identity and realm roles |
| `GET /api/v1/patients?q=` | Search/list authorised patients |
| `POST /api/v1/patients` | Create a synthetic patient (admin) |
| `GET /api/v1/patients/{id}` | Read patient |
| `GET /api/v1/patients/{id}/permissions` | Effective patient permissions for UI |
| `GET /api/v1/patients/{id}/observations` | Read local observations |
| `GET /api/v1/patients/{id}/timeline` | Read imported FHIR timeline |
| `GET /api/v1/patients/{id}/insights` | Generate local deterministic context report |
| `POST /api/v1/patients/{id}/fhir/sync` | Publish local observations and import supported resources |
| `GET /api/v1/patients/{id}/fhir` | Search the FHIR Patient |
| `GET /api/v1/patients/{id}/snapshots` | List twin snapshots |
| `POST /api/v1/patients/{id}/snapshots` | Create immutable snapshot |
| `GET /api/v1/patients/{id}/snapshots/{snapshot_id}` | Retrieve and verify snapshot artifact |
| `GET /api/v1/patients/{id}/simulations` | List scenario runs |
| `POST /api/v1/patients/{id}/simulations` | Run and persist a deterministic scenario |
| `GET /api/v1/patients/{id}/access-grants` | List grants (admin) |
| `POST /api/v1/patients/{id}/access-grants` | Create/update grant (admin) |
| `DELETE /api/v1/patients/{id}/access-grants/{grant_id}` | Revoke grant (admin) |
| `GET /api/v1/audit/events` | Read audit events (admin) |

## Demo identities

These credentials are development-only. Keycloak forces a password change on first login. Do not expose this realm or retain these users in a shared or production environment.

- Clinician: `demo.clinician` / `Demo-Only-Change-Me-2026!` (write grant to SYN-0001)
- Researcher: `demo.researcher` / `Demo-Research-Change-Me-2026!` (read-only grant to SYN-0001)
- Administrator: `demo.admin` / `Demo-Admin-Change-Me-2026!` (platform-wide access)

## Automated tests

The API test suite covers patient access isolation, patient permission reporting, registry create/search, administrator grant management, simulation persistence/formula output, FHIR resource import and patient-reference verification, snapshot integrity/immutability and audit event creation.

The live HAPI integration test also publishes the six local synthetic observations to a running HAPI FHIR R4 server before exercising resource ingestion. CI now includes:
- Python API tests plus live HAPI FHIR integration.
- Next.js production build.
- Compose graph validation and API/web container image builds.

A passing API test suite does not certify the browser experience, infrastructure security, clinical correctness or production readiness. The new combined CI results must be reviewed for the commit that contains these changes.

Run API tests locally:

```powershell
cd services/api
python -m pip install -r requirements-dev.txt
$env:DATABASE_URL = "sqlite:///./test.db"
$env:AUTH_REQUIRED = "false"
pytest -q
```

## Remaining milestones and production blockers

The following work is not represented as complete:

- Formal Alembic migrations and upgrade/downgrade testing.
- Production Keycloak configuration, TLS, secrets management and non-demo identities.
- HAPI FHIR production database, authentication, SMART-on-FHIR/OAuth policy, terminology/profile validation, backup and HA.
- Broader FHIR coverage such as MedicationRequest, DiagnosticReport, CarePlan, DocumentReference and AllergyIntolerance.
- Clinically validated simulation models, review workflow and model version governance.
- Private local LLM runtime, patient-scoped RAG, evidence citations and model/prompt/tool version registry.
- MCP server with identity propagation, patient-level authorisation and audit enforcement.
- Dedicated observability stack: OpenTelemetry collector, Prometheus, Grafana, centralised logs, dashboards and alerting.
- Security review, threat modelling, penetration testing, disaster recovery exercise and clinical safety/regulatory assessment.
- Full browser E2E tests across login, registry, FHIR sync, snapshot, scenario and governance flows.
- SBOM, formal dependency update policy, vulnerability scanning and licence review.

See [Production readiness assessment](PRODUCTION-READINESS.md). The project must use synthetic data only until the required controls and approvals are completed.

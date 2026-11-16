# MVP implementation status

## Implemented in this milestone
- Next.js 15 / React 19 dashboard with Keycloak browser login using the authorization-code flow and PKCE.
- Keycloak development realm imported from `infrastructure/keycloak/realm-twinfixeno.json`.
- Synthetic demo clinician account and realm roles for local development.
- FastAPI bearer-token authentication with RS256 signature, issuer and audience validation against Keycloak JWKS.
- Authenticated patient, observation and snapshot API routes.
- HAPI FHIR R4 server container.
- FHIR capability-statement health check.
- Idempotent synchronisation of the synthetic application patient to a FHIR `Patient` resource.
- FHIR Patient search by stable twinfixeno identifier.
- PostgreSQL persistence, APISIX routes and Docker Compose orchestration.

## Local identity setup
- Keycloak: http://localhost:8081
- Realm: `twinfixeno`
- Web client: `twinfixeno-web` (public OIDC client, PKCE)
- API audience: `twinfixeno-api`
- Demo user: `demo.clinician`
- Temporary development password is declared in the realm import file. Keycloak requires a password change at first login.
- Bootstrap administrator credentials are configured through `.env`; change the example password before use.

## FHIR endpoints
- HAPI FHIR base URL inside Compose: `http://fhir:8080/fhir`
- Host capability statement: http://localhost:8090/fhir/metadata
- Authenticated API status: `GET /api/v1/integrations/fhir/status`
- Sync synthetic patient to FHIR: `POST /api/v1/patients/{id}/fhir/sync`
- Find matching FHIR Patient: `GET /api/v1/patients/{id}/fhir`

## Important limitations
- This is a development identity configuration, not a production IAM deployment.
- Demo user credentials and bootstrap defaults must be changed. Do not expose this environment to the public internet.
- Realm roles are exposed in the authenticated principal, but fine-grained role-based policies and patient-level authorisation have not yet been implemented.
- The current FHIR integration synchronises only a synthetic Patient resource. It does not ingest Observations, Conditions, Encounters, MedicationRequests or DiagnosticReports.
- HAPI FHIR uses its development container configuration; persistent production database configuration, backups and security hardening remain future work.
- No automated integration test suite or container build verification has been run in this environment.

## Remaining work
- Fine-grained role and patient-level authorisation policies.
- FHIR Observation and other clinical resource ingestion with validation.
- Formal Alembic migrations.
- Immutable snapshot payload and detailed provenance.
- Simulation engine and scenario model.
- Qdrant, object storage, local LLM, RAG and MCP.
- OpenTelemetry, Prometheus, Grafana and Loki.
- Automated test suite and CI pipeline.

The demo patient is fictional. Do not add real patient information.

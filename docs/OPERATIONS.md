# twinfixeno operations guide

## What this stack includes

The default Compose stack brings up the browser workspace, FastAPI service, PostgreSQL application database, Keycloak identity provider (with its own persistent PostgreSQL database), APISIX API gateway and HAPI FHIR R4 server.

The workspace modules are:
- Overview and assigned patient registry.
- Observation measurements and FHIR-backed clinical timeline.
- Patient-scoped FHIR Patient synchronisation and Observation, Condition and Encounter ingestion.
- Immutable snapshot creation, version history, payload inspection, SHA-256 verification and source provenance.
- Administrator-only access-grant listing, creation/update and revocation.
- Role and patient-grant enforcement at the API boundary.

The AI copilot and physiological simulation engine are not implemented in this release. They are intentionally not presented as working modules.

## Run the complete local stack

Requirements: Docker Desktop with the Linux container engine enabled (WSL 2 on Windows).

From the repository root:

\`\`\`powershell
Copy-Item .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
\`\`\`

The first build downloads the base images and Node/Python dependencies. Check startup output with:

\`\`\`powershell
docker compose logs -f web api keycloak fhir
\`\`\`

Open these local endpoints:

| Module | URL |
|---|---|
| Workspace | http://localhost:3000 |
| API documentation | http://localhost:8000/docs |
| API readiness | http://localhost:8000/health/ready |
| APISIX API gateway | http://localhost:9080 |
| Keycloak | http://localhost:8081 |
| HAPI FHIR metadata | http://localhost:8090/fhir/metadata |

The browser uses the public URLs supplied by the Next.js runtime endpoint at \`/runtime-config\`. If you change a browser-visible URL in \`.env\`, recreate the web container:

\`\`\`powershell
docker compose up -d --force-recreate web
\`\`\`

## Demo accounts

The imported development realm contains:
- \`demo.admin\` — platform-wide patient access and access-grant administration.
- \`demo.clinician\` — write access to the seeded synthetic patient.
- \`demo.researcher\` — read-only access to the seeded synthetic patient.

The realm forces a password change on first login. These are development-only identities and must never be retained in a production realm. Change the bootstrap administrator password and both database passwords in \`.env\` before exposing even a development instance on a shared network.

## Data and persistence

PostgreSQL application data and Keycloak identity data use separate named Docker volumes. Do not run \`docker compose down -v\` unless you explicitly intend to delete both databases and all locally stored snapshots and user identities.

Useful commands:

\`\`\`powershell
docker compose ps
docker compose logs --tail 200 api
docker compose logs --tail 200 keycloak
docker compose restart api
docker compose down
\`\`\`

The bundled HAPI service is for development/integration testing. Treat it as disposable unless you separately configure and verify durable FHIR persistence, backups, authentication and restore procedures. The application PostgreSQL volume does not contain the HAPI repository's data.

## Security model

| Identity | Patient scope | Read | Write |
|---|---|---:|---:|
| \`twinfixeno-admin\` | All patients | Yes | Yes |
| \`clinician\` | Explicit patient grant | Yes | Only with write grant |
| \`researcher\` | Explicit patient grant | Yes | No |
| Other / no role | None | No | No |

Patient visibility, read/write permissions and administrator-only grant management are checked by FastAPI; hiding a frontend control is not used as the security boundary.

## Production deployment gate — do not skip

The default \`compose.yaml\` is a local development/demo deployment, not a production deployment. It uses Keycloak development mode, an imported demo realm and demo identities; HTTP localhost endpoints; example secrets; and a development HAPI FHIR image configuration. Do not expose these ports to the public internet and do not load real patient data.

Before a real clinical or production deployment, complete and independently verify at least:
1. Production Keycloak mode, externally managed realm/client configuration, MFA, password/session policies, production hostname and TLS.
2. Secret management and rotation; remove demo identities and all sample credentials.
3. TLS and network segmentation for the web, API, database, identity provider and FHIR endpoints; remove direct host exposure of internal services.
4. A secured, durable FHIR R4 deployment with service authentication, database persistence, encryption, backup/restore, availability and retention controls.
5. Versioned database migrations and a tested migration/rollback process; the current MVP still creates its initial schema from SQLAlchemy metadata.
6. Formal audit events for authentication, patient access, FHIR imports, grant changes, exports and snapshot operations, with protected retention.
7. Patient consent, purpose-of-use, care-team/tenant boundaries, delegated access and emergency break-glass workflows.
8. Signed snapshot attestations and protected signing-key custody if cryptographic proof of origin is required; SHA-256 alone is an integrity checksum.
9. Centralised logs, metrics, alerting, vulnerability scanning, dependency/image patching, rate limiting, threat modelling and disaster-recovery exercises.
10. Clinical safety review, data-quality/terminology validation, privacy impact assessment, regulatory review and approval by the deploying organisation.

This repository is a synthetic-data software MVP. It is not a medical device and has not been clinically validated or certified. It must not be used to diagnose, treat or make patient-care decisions.

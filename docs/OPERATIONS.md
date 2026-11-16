# twinfixeno local operations

## Start the complete synthetic-data stack

Prerequisites: Docker Desktop with the Linux container engine enabled (WSL 2 on Windows).

From the repository root:

\`\`\`powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config
docker compose up --build -d
docker compose ps
\`\`\`

The first run downloads the images and builds the web/API containers. The Compose dependency graph waits for PostgreSQL, Keycloak and HAPI FHIR readiness before the API is started, then waits for API readiness before starting the web workspace.

## Local URLs

| Module | URL |
|---|---|
| Web workspace | http://localhost:3000 |
| FastAPI / OpenAPI | http://localhost:8000/docs |
| API readiness | http://localhost:8000/health/ready |
| APISIX gateway | http://localhost:9080 |
| Keycloak | http://localhost:8081 |
| HAPI FHIR capability statement | http://localhost:8090/fhir/metadata |
| Local Ollama API | http://localhost:11434 |
| Qdrant dashboard | http://localhost:6333/dashboard |
| MCP Streamable HTTP | http://localhost:8001/mcp |

All host port bindings are restricted to loopback (127.0.0.1). The browser loads API and Keycloak addresses from the Next.js /runtime-config route, so WEB_API_BASE_URL and WEB_KEYCLOAK_URL in .env are read when the container starts, not baked into the JavaScript bundle.

## Demo users

The development realm includes:
- demo.admin — administrator and patient grant management.
- demo.clinician — clinician with write access to the seeded synthetic patient.
- demo.researcher — read-only access to the seeded synthetic patient.

Keycloak forces a password change at first login. These demo identities and bootstrap credentials are for local development only.

## Useful commands

\`\`\`powershell
docker compose ps
docker compose logs -f web api keycloak fhir
docker compose logs --tail 200 api
docker compose restart api
docker compose down
\`\`\`

The application and Keycloak identity stores run in separate PostgreSQL services, each backed by its own named volume. Both preserve data across ordinary container recreation. Do not use docker compose down -v unless you intend to delete the local application database, identity store and snapshot history.

## What the integrated release contains

- Keycloak OIDC login, role-aware UI and patient-level API authorisation.
- Patient registry search and administrator-only synthetic patient creation.
- Patient summary and latest observations.
- FHIR Patient upsert, local synthetic Observation publication, and Observation/Condition/Encounter import.
- FHIR-backed clinical timeline with source identity, version and timestamp.
- Immutable snapshot history, artifact/provenance inspection and SHA-256 verification.
- Persisted percentage-delta simulation runs, explicitly labelled hypothetical.
- Local Ollama LLM, nomic-embed-text embeddings and patient-filtered Qdrant RAG.
- MCP Streamable HTTP tools forwarding caller Keycloak tokens; API patient grants remain enforced.
- Deterministic context report retained as a fallback.
- Administrator patient access grants and application audit-event review.

The clinically validated physiology simulator and enterprise observability stack are not implemented in this release. They are not displayed or described as working AI services.

## Production deployment status

This Compose profile is a local synthetic-data development/review environment. It is not approved for production or real patient data. See PRODUCTION-READINESS.md for the full go-live blockers.

At minimum, production requires production-mode identity and MFA, TLS, managed secrets, network segmentation, supported persistent FHIR deployment, database migrations, backup/restore and HA, consent/purpose-of-use/care-team controls, independent audit retention, security testing, monitoring, clinical safety validation and relevant regulatory/privacy approvals.

Never load identifiable patient data into this local demo stack.

## Local LLM, RAG and MCP

Compose starts Ollama, downloads `nomic-embed-text` and `llama3.2:3b` into the persistent model volume, starts Qdrant with persistent vector storage, and starts the MCP Streamable HTTP server. First startup downloads several GB and can take several minutes.

After login, check `GET /api/v1/ai/status`; index a patient using `POST /api/v1/patients/{id}/rag/index` (write grant required), then query `POST /api/v1/patients/{id}/rag/query` with `{"question":"Summarise the recorded observations","top_k":5}`. Results include source records and SHA-256 hashes. MCP URL: `http://localhost:8001/mcp`; tools: `get_patient_timeline`, `index_patient_evidence`, `ask_patient_evidence`. MCP forwards the caller's bearer token to the API, so normal Keycloak roles and patient grants apply.

RAG retrieval is filtered by patient ID. The model is instructed to answer only from retrieved records and not diagnose or recommend treatment. Synthetic data only; not clinical decision support.

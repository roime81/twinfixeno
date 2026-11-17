# twinfixeno local operations

## Start the complete synthetic-data stack

Prerequisites: Docker Desktop with the Linux container engine enabled (WSL 2 on Windows).

From the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config
docker compose up --build -d
docker compose ps
```

The API container runs `alembic upgrade head` before serving requests; the initial metadata baseline creates missing tables and installs PostgreSQL immutability triggers without dropping pre-existing tables. It does not alter columns in an already-created table, so schema drift must be handled through a reviewed migration. `SEED_DEMO_DATA=true` creates the `SYN-0001` demonstration patient and grants, then runs an idempotent batch loader controlled by `SEED_SYNTHETIC_PATIENTS` (default `10000`). The loader ensures patient IDs `SYN-0001` through `SYN-10000` and six synthetic observations per patient, about 60,000 observation rows in total. It skips existing patient IDs and can safely run again after restarts. Set `SEED_DEMO_DATA=false` to skip both demo and generated data. The first run downloads the images and builds the web/API/MCP containers. The Compose dependency graph waits for PostgreSQL, Keycloak, HAPI FHIR and Qdrant readiness, then pulls the Ollama chat and embedding models before starting the API and web workspace. The first model download can take several minutes and requires several GB of network transfer and disk space. The browser sends API traffic through APISIX on port 9080; FastAPI port 8000 is retained for OpenAPI and diagnostics.

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
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 |
| Jaeger trace viewer | http://localhost:16686 |

All host port bindings are restricted to loopback (127.0.0.1). The browser loads API and Keycloak addresses from the Next.js /runtime-config route, so WEB_API_BASE_URL and WEB_KEYCLOAK_URL in .env are read when the container starts, not baked into the JavaScript bundle.

The local example enables username matching only for the seeded demo identities via `ALLOW_USERNAME_PATIENT_GRANTS=true`. In a shared/production environment set it to `false` and create grants using the immutable Keycloak subject ID. The API defaults to subject-only matching when this variable is absent.

## Demo identities

Use the demo administrator when testing all administrator-only screens and actions:
- `demo.admin` — `Demo-Admin-Change-Me-2026!` (platform-wide synthetic-patient access and grant management)
- `demo.clinician` — `Demo-Only-Change-Me-2026!` (write access to SYN-0001)
- `demo.researcher` — `Demo-Research-Change-Me-2026!` (read-only access to SYN-0001)

Keycloak forces a password change at first login. These credentials are public development fixtures, never use them outside the local demo environment. Sign out before switching roles.

## Verify the synthetic PostgreSQL dataset

The application database is the `postgres` Compose service. Verify the loaded records with:

```powershell
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) AS patients FROM patients WHERE left(external_id,4)=chr(83)||chr(89)||chr(78)||chr(45);"'
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) AS observations FROM observations;"'
```

The registry uses server-side search and pagination. Administrators can search all synthetic records; clinicians and researchers see only patients with a matching patient-level grant. The seeded clinician and researcher intentionally receive access only to `SYN-0001`.

## Useful commands

```powershell
docker compose ps
docker compose logs -f web api keycloak fhir
docker compose logs --tail 200 api
docker compose restart api
docker compose down
```

The application, Keycloak identity and HAPI FHIR data stores run in separate PostgreSQL services, each backed by its own named volume. All three preserve data across ordinary container recreation. Do not use docker compose down -v unless you intend to delete the application database, identity store, FHIR resources, AI vectors, model cache and snapshot history.

## Monitoring and tracing

Prometheus scrapes the API's internal `/metrics` endpoint. Grafana provisions the TwinFixeno operations dashboard and Prometheus/Jaeger data sources. Jaeger receives HTTP request spans and AI indexing/query spans. The spans carry model/prompt/retrieval versions and content hashes, not question/answer bodies or bearer tokens. Host ports are loopback-only. Grafana local demo credentials are `admin` / `local-grafana-password`; change them before sharing this environment. Use `docker compose logs` for container logs; this release does not provide central log aggregation, SIEM forwarding or alert notification routing.

The Grafana dashboard shows API availability, request throughput, 5xx rate, p95 latency, RAG query rate, FHIR sync outcomes and snapshot operations. Jaeger provides request and AI trace search for service `twinfixeno-api`.

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

The current percentage-delta scenario is arithmetic only, not a physiology simulator. Prometheus metrics, Grafana dashboards and Jaeger request/AI traces are bundled for local operations. Centralised log aggregation/SIEM, model/prompt/tool rollback registry and clinical AI evaluation remain outstanding.

## Production deployment status

This Compose profile is a local synthetic-data development/review environment. It is not approved for production or real patient data. See PRODUCTION-READINESS.md for the full go-live blockers.

At minimum, production requires production-mode identity and MFA, TLS, managed secrets, network segmentation, supported persistent FHIR deployment, database migrations, backup/restore and HA, consent/purpose-of-use/care-team controls, independent audit retention, security testing, monitoring, clinical safety validation and relevant regulatory/privacy approvals.

Never load identifiable patient data into this local demo stack.

## Local LLM, RAG and MCP

Compose starts Ollama, downloads `nomic-embed-text` and `qwen2.5:3b` into the persistent model volume, starts Qdrant with persistent vector storage, and starts the MCP Streamable HTTP server. First startup downloads several GB and can take several minutes.

After login, check `GET /api/v1/ai/status`; index a patient using `POST /api/v1/patients/{id}/rag/index` (write grant required), then query `POST /api/v1/patients/{id}/rag/query` with `{"question":"Summarise the recorded observations","top_k":5}`. Results include source records and SHA-256 hashes. MCP URL: `http://localhost:8001/mcp`; tools: `get_patient_timeline`, `index_patient_evidence`, `ask_patient_evidence`. MCP forwards the caller's bearer token to the API, so normal Keycloak roles and patient grants apply.

RAG retrieval is filtered by patient ID. The model is instructed to answer only from retrieved records and not diagnose or recommend treatment. Synthetic data only; not clinical decision support.


## Troubleshooting

- **`docker` is not recognized:** install Docker Desktop, restart PowerShell and verify `docker compose version`.
- **Docker daemon unavailable:** start Docker Desktop and wait for the engine to report running.
- **Web/API starts late or is unhealthy:** run `docker compose ps` and `docker compose logs --tail 200 ollama-models api web`. API and web depend on the Ollama model-pull job completing.
- **Evidence Assistant reports AI unavailable:** inspect `docker compose logs ollama ollama-models qdrant api`; wait for both model downloads to complete, then reload the workspace and use Check local AI status.
- **Keycloak login loops or token rejected:** use the local Keycloak URL from this same browser host and confirm the configured issuer is `http://localhost:8081/realms/twinfixeno`.
- **Gateway API calls fail:** test `http://localhost:9080/health` and verify `docker compose logs apisix`. The web app uses APISIX, not the direct API port.

After changing code or Compose configuration, rebuild with `docker compose up --build -d`. Preserve named volumes with `docker compose down`; do not add `-v` unless intentionally deleting local data.

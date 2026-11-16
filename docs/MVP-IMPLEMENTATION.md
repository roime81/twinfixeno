# MVP implementation status

## Implemented
- Next.js 15 / React 19 dashboard shell.
- FastAPI service with health, patient, observation and snapshot endpoints.
- PostgreSQL persistence using SQLAlchemy.
- Idempotent synthetic demo patient and observation seed.
- Apache APISIX declarative API routes.
- Docker Compose local deployment.

## Not yet implemented
- Keycloak authentication and patient-level authorisation.
- HAPI FHIR integration and FHIR profile validation.
- Formal Alembic database migrations.
- Immutable snapshot payload and detailed provenance.
- Simulation engine and scenario model.
- Qdrant, object storage, local LLM, RAG and MCP.
- OpenTelemetry, Prometheus, Grafana and Loki.
- Automated test suite and CI pipeline.

The demo patient is fictional. Do not add real patient information.

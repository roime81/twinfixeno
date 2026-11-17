# Production readiness assessment

**Status: NOT APPROVED FOR PRODUCTION OR REAL PATIENT DATA.**

Use [GO-LIVE-ACCEPTANCE.md](GO-LIVE-ACCEPTANCE.md) as the evidence and sign-off register for Information Security, Platform Operations/SRE, Privacy/Data Governance and Clinical Safety.

The integrated Compose stack is a runnable synthetic-data development/review environment. Its local seed contains 10,000 fictional patient records and approximately 60,000 fictional observation rows in PostgreSQL. It is not a production deployment. Synthetic names and values are generated for testing and must never be treated as real clinical histories. Passing unit/API tests does not change this status.

## What this release can demonstrate

- OIDC login and API JWT verification.
- Patient-level read/write grants.
- Synthetic patient registry workflows.
- FHIR Patient synchronisation and synthetic Observation publication.
- Patient-scoped Observation/Condition/Encounter import and timeline.
- Append-only twin snapshot artifacts with SHA-256 checksums and provenance.
- Deterministic percentage-delta scenarios with explicit assumptions (not a physiological model).
- Local Ollama chat and embedding models, patient-filtered Qdrant RAG and source references.
- MCP Streamable HTTP with timeline, evidence-indexing and evidence-query tools that forward caller tokens to the API.
- Deterministic local context report as a fallback.
- Application-level audit events.
- One-command local Compose startup.

## Blockers before any production deployment

### Identity and network security
- Replace Keycloak `start-dev` and the development realm with a production Keycloak deployment and reviewed realm/client configuration.
- Set `SEED_DEMO_DATA=false` and `ALLOW_USERNAME_PATIENT_GRANTS=false`, remove demo identities and bootstrap passwords, and replace the development realm. Enforce approved MFA, password, session, account lifecycle and privileged-access controls.
- Deploy TLS for every browser and service boundary. Configure exact public hostnames, OIDC issuer, redirect URIs, trusted proxy and cookie settings.
- Do not expose API, HAPI FHIR or database ports directly to untrusted networks. Put ingress behind an approved reverse proxy/WAF and apply gateway rate limits and request-size limits.
- Rotate all default credentials, use a secret manager, and verify no secrets are present in Compose files, images, CI logs or Git history.

### Healthcare data governance
- Do not load real patient information into this development environment.
- Define tenancy, care-team relationship, purpose-of-use, consent, break-glass access, delegated access, patient identity matching and retention policies.
- Validate FHIR profiles, terminology bindings, resource provenance, patient matching and data-quality rules with the receiving clinical systems.
- Complete privacy impact assessment, clinical safety assessment and applicable Malaysian legal/regulatory review before processing identifiable health data.

### Persistence and recovery
- The repository now has an initial Alembic baseline that creates/adopts the current schema and installs PostgreSQL immutability triggers. CI exercises upgrade → downgrade → upgrade on SQLite. Before production, replace the metadata-based baseline with reviewed explicit revisions for every future schema change, rehearse production PostgreSQL upgrade/rollback (or forward-fix) procedures, and run migrations as a controlled deployment job.
- The local Compose environment now gives HAPI FHIR its own PostgreSQL 16 database and persistent volume. Production still requires an approved managed database topology, TLS, encryption at rest, backup/restore tests, retention, high availability and disaster recovery objectives.
- Add independent tamper-evident audit storage and access reviews. The current audit table and snapshot SHA-256 checksum are not a signed, independently immutable evidence system.
- Define operational ownership, SLOs, incident response, patching, vulnerability management and dependency/SBOM processes. A local Prometheus/Grafana/Jaeger stack is bundled, but production retention, alert routing, centralised logs, SIEM forwarding and secured monitoring access require deployment-specific configuration.

### AI and simulation safety
- The local AI path is implemented for synthetic-data demonstration: Ollama serves Qwen 2.5 3B and nomic-embed-text; Qdrant stores embeddings; API retrieval filters by patient ID; MCP forwards caller bearer tokens to the API.
- The current Evidence Assistant is not a validated clinical assistant. Prompt/retrieval versions and Ollama artifact digests are attached to results; the audit record stores model, prompt, retrieval and answer digest metadata without storing question/answer text. Citation correctness is not automatically verified. Prompt instructions are not a security barrier. There is no production model registry, independent evaluation harness, adversarial prompt-injection testing, clinical review workflow, full trace correlation or validated clinical safety case.
- The MCP server currently exposes only timeline, evidence-indexing and evidence-query tools. It is not an enterprise agent platform and does not provide its own authorization boundary.
- The current simulation is a percentage-delta arithmetic calculation. It must not be presented as a physiological model or used to influence diagnosis/treatment.
- Before any clinical use, require representative evaluations, access-control tests, threat modelling, human oversight, data lineage, rollback, model-change governance and formal clinical safety/regulatory review.

### Verification
- Run the new CI workflow on the release commit and resolve all failures.
- Add browser-level tests for real OIDC login, patient selection, role-specific actions, FHIR sync, snapshot creation/verification, scenario persistence and admin grant/audit views.
- Perform security testing with positive and negative cross-patient access cases and production-like identity/network configuration.
- Verify that all containers have health checks, non-root execution where supported, resource limits, image pinning/digests, log rotation and tested recovery procedures. Add a browser-level Playwright suite for real Keycloak login, role-specific controls, patient switching (including no stale cross-patient display), FHIR sync, RAG indexing/querying, snapshot verification and audit review.

## Go-live decision

A production go-live requires sign-off from application engineering, infrastructure/platform operations, information security, privacy/data governance and clinical safety owners. This repository does not make or imply those approvals.

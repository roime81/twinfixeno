# Production readiness assessment

**Status: NOT APPROVED FOR PRODUCTION OR REAL PATIENT DATA.**

The integrated Compose stack is a runnable synthetic-data development/review environment. It is not a production deployment. Passing unit/API tests does not change this status.

## What this release can demonstrate

- OIDC login and API JWT verification.
- Patient-level read/write grants.
- Synthetic patient registry workflows.
- FHIR Patient synchronisation and synthetic Observation publication.
- Patient-scoped Observation/Condition/Encounter import and timeline.
- Append-only twin snapshot artifacts with SHA-256 checksums and provenance.
- Deterministic percentage-delta scenarios with explicit assumptions.
- Local data-summary report.
- Application-level audit events.
- One-command local Compose startup.

## Blockers before any production deployment

### Identity and network security
- Replace Keycloak `start-dev` and the development realm with a production Keycloak deployment and reviewed realm/client configuration.
- Remove demo identities and bootstrap passwords. Enforce approved MFA, password, session, account lifecycle and privileged-access controls.
- Deploy TLS for every browser and service boundary. Configure exact public hostnames, OIDC issuer, redirect URIs, trusted proxy and cookie settings.
- Do not expose API, HAPI FHIR or database ports directly to untrusted networks. Put ingress behind an approved reverse proxy/WAF and apply gateway rate limits and request-size limits.
- Rotate all default credentials, use a secret manager, and verify no secrets are present in Compose files, images, CI logs or Git history.

### Healthcare data governance
- Do not load real patient information into this development environment.
- Define tenancy, care-team relationship, purpose-of-use, consent, break-glass access, delegated access, patient identity matching and retention policies.
- Validate FHIR profiles, terminology bindings, resource provenance, patient matching and data-quality rules with the receiving clinical systems.
- Complete privacy impact assessment, clinical safety assessment and applicable Malaysian legal/regulatory review before processing identifiable health data.

### Persistence and recovery
- Add Alembic migrations, tested upgrade/rollback paths and a controlled migration job. `Base.metadata.create_all` is not a production migration strategy.
- Configure supported production PostgreSQL and HAPI FHIR databases, encryption at rest, backup schedules, restore tests, retention, high availability and disaster recovery objectives.
- Add independent tamper-evident audit storage and access reviews. The current audit table and snapshot SHA-256 checksum are not a signed, independently immutable evidence system.
- Define operational ownership, SLOs, incident response, patching, vulnerability management and dependency/SBOM processes.

### AI and simulation safety
- The current Evidence Assistant is a deterministic summary, not an LLM or RAG implementation.
- No MCP server, model gateway, vector database or local model runtime is included in this release.
- The current simulation is a percentage-delta calculation. It must not be presented as a physiological model or used to influence diagnosis/treatment.
- Any future model requires evidence traceability, access-control propagation, prompt/model/tool versioning, evaluation, rollback, human review and clinical validation.

### Verification
- Run the new CI workflow on the release commit and resolve all failures.
- Add browser-level tests for real OIDC login, patient selection, role-specific actions, FHIR sync, snapshot creation/verification, scenario persistence and admin grant/audit views.
- Perform security testing with positive and negative cross-patient access cases and production-like identity/network configuration.
- Verify that all containers have health checks, non-root execution where supported, resource limits, image pinning/digests, log rotation and tested recovery procedures.

## Go-live decision

A production go-live requires sign-off from application engineering, infrastructure/platform operations, information security, privacy/data governance and clinical safety owners. This repository does not make or imply those approvals.

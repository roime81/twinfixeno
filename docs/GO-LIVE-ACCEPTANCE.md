# TwinFixeno production go-live acceptance register

**Current disposition: NOT APPROVED FOR PRODUCTION OR REAL PATIENT DATA.**

This register separates automated engineering evidence from decisions that require named organisational owners. A green CI run is necessary but does not constitute security, operational, privacy or clinical approval.

## 1. Release candidate facts

| Item | Current state |
|---|---|
| Intended deployment | Local development/review Compose profile |
| Application database | PostgreSQL 16, persistent named volume |
| Identity database | Separate PostgreSQL 16 for Keycloak |
| FHIR database | Separate PostgreSQL 16 for HAPI FHIR |
| Synthetic dataset | 10,000 synthetic patient IDs (SYN-0001 to SYN-10000); six observations per patient |
| Data classification | Entire seeded dataset is fictional test data |
| Clinical purpose | Not clinical decision support; no diagnosis, treatment recommendation or physiological prediction |
| Production status | Not approved |

## 2. Engineering acceptance evidence

These are machine-verifiable gates. Record the release SHA and links to completed Actions runs before accepting a release candidate.

| Gate | Evidence required | Status |
|---|---|---|
| API and live FHIR tests | Pytest report; migration upgrade/downgrade/upgrade; live HAPI R4 integration | CI |
| MCP contract and security | Initialize/tools-list handshake; caller token forwarding; unauthenticated call rejection; sanitized errors | CI |
| Web production build | npm run build result | CI |
| Compose startup | All services healthy and service probes pass | CI |
| FHIR persistence | Synthetic Patient survives HAPI container restart | CI |
| Dataset integrity | PostgreSQL counts: 10,000 SYN patients and 60,000 observations; repeated seed adds zero rows | CI + database query |
| Browser role workflows | Clinician, administrator and researcher Playwright reports; screenshots/traces on failures | Pending clean run |
| Browser patient isolation | Search, select a patient, switch patients, verify no previous patient's state remains visible | Add/verify explicit E2E case |

## 3. Information security approval

**Required accountable approver:** Information Security / CISO delegate.

Evidence and controls to provide before sign-off:

- Production threat model covering web, APISIX, FastAPI, Keycloak, PostgreSQL, HAPI FHIR, Ollama, Qdrant and MCP.
- Independent penetration test and remediation evidence for authentication, authorization, patient-ID enumeration, cross-patient access, session handling, injection, SSRF, prompt injection and MCP tool invocation.
- Production Keycloak (not start-dev), MFA, privileged account controls, account lifecycle, reviewed OIDC client/redirect configuration and token/session policy.
- TLS and certificate lifecycle for all ingress and service boundaries; network segmentation; no public database, API, FHIR, Ollama or Qdrant ports.
- Secrets manager, credential rotation and proof that no secrets are present in source, images, build logs or runtime diagnostics.
- SAST, dependency/SCA, container image, IaC and secret scanning with an agreed vulnerability SLA; SBOM and pinned image digests.
- Enforced immutable-subject patient grants. Disable ALLOW_USERNAME_PATIENT_GRANTS; verify no username-only grants are used in production.
- Security review of audit retention, privileged operations, monitoring access and log redaction.

**Approval record**

| Field | Entry |
|---|---|
| Reviewer name / role | |
| Evidence / report links | |
| Open findings and accepted risk | |
| Decision (approve / reject / conditional) | |
| Date | |
| Signature / approval reference | |

## 4. Platform operations approval

**Required accountable approver:** Platform Operations / SRE service owner.

Evidence and controls to provide before sign-off:

- Approved production topology, capacity plan and infrastructure ownership for application, identity and FHIR databases, AI serving, vector storage and ingress.
- PostgreSQL backup schedule, encryption, retention, point-in-time recovery where required, and witnessed restore tests for all three databases.
- HAPI FHIR backup/restore, migration, indexing and recovery runbooks; verified resource persistence and FHIR service-level objectives.
- Defined RTO/RPO, availability/latency/error SLOs, capacity thresholds and service dependency/health model.
- Central log aggregation, SIEM forwarding, trace/metric retention, alert routing and on-call escalation. Local Grafana/Prometheus/Jaeger is not a production monitoring service by itself.
- Deployment, migration, rollback/forward-fix, patching, vulnerability response, incident management and disaster-recovery exercises.
- Resource limits, non-root execution, image provenance, log rotation, storage capacity and tested scale/load behaviour for the target patient volume and workload.

**Approval record**

| Field | Entry |
|---|---|
| Service owner / role | |
| Backup and restore evidence | |
| RTO / RPO / SLO references | |
| Runbook and on-call references | |
| Open risks / exceptions | |
| Decision (approve / reject / conditional) | |
| Date | |
| Signature / approval reference | |

## 5. Privacy and data governance approval

**Required accountable approver:** Data Protection Officer / Privacy and Data Governance owner.

- Confirm lawful purpose, data classification, minimum necessary data, collection/sharing basis and approved data flows.
- Complete privacy impact assessment and applicable Malaysian privacy/regulatory review.
- Approve data retention, deletion, access review, subject rights, disclosure, third-party processing and cross-border controls.
- Define patient matching, tenancy, care-team relationships, consent, purpose-of-use and break-glass policy.
- Confirm AI prompts, embeddings, retrieved evidence, telemetry and logs have approved data handling and retention boundaries.

**Approval record**

| Field | Entry |
|---|---|
| Reviewer name / role | |
| PIA / governance references | |
| Approved data flows and retention | |
| Open risks / exceptions | |
| Decision (approve / reject / conditional) | |
| Date | |
| Signature / approval reference | |

## 6. Clinical safety and product approval

**Required accountable approver:** Clinical Safety Officer / designated clinical governance committee.

- Approve the intended purpose, users, clinical setting, population, exclusions and claims made by the product.
- Complete clinical hazard analysis, risk controls, usability assessment, human-factors review and a documented safety case.
- Validate source mappings, FHIR profiles, terminology, observation units, timestamp handling, provenance and data quality with clinical system owners.
- If AI or simulation is to influence care, conduct representative clinical evaluation, subgroup/bias analysis, independent model/citation validation, prompt-injection testing, human oversight and model-change/rollback governance.
- Define escalation, override, review, accountability and post-deployment monitoring.
- Determine applicable medical-device/software regulatory status and obtain required approvals before any clinical use.

The current percentage-delta engine is arithmetic only. The Evidence Assistant is retrieval over synthetic data and is not validated clinical decision support. Neither may be used to diagnose, recommend treatment or influence care.

**Approval record**

| Field | Entry |
|---|---|
| Clinical safety owner / role | |
| Intended purpose and exclusions | |
| Hazard analysis / safety case | |
| Clinical evaluation references | |
| Regulatory / governance decision | |
| Open risks / exceptions | |
| Decision (approve / reject / conditional) | |
| Date | |
| Signature / approval reference | |

## 7. Go-live decision

Production go-live is blocked until all applicable approval records above are completed, open findings are closed or formally accepted by the accountable owner, and the release candidate has passed the engineering gates against the same commit SHA that will be deployed.

No approval is implied by this template or by passing CI. Do not load identifiable patient data into the local development stack.

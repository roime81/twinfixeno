# TWINFixeno

**An open-source, privacy-first healthcare Digital Twin platform.**

TWINFixeno is an early-stage, design-driven MVP for creating a longitudinal digital representation of a patient's health journey. It brings together interoperable clinical data, versioned patient-state snapshots, explainable analytics, hypothetical scenario exploration, private local language models and governed Model Context Protocol (MCP) tools.

> **Project status:** Integrated synthetic-data development MVP. The web workspace provides patient registry, timeline, illustrative simulation, snapshot inspection, governance and a local Evidence Assistant. The AI path uses Ollama (Qwen 2.5 3B), `nomic-embed-text` embeddings and patient-filtered Qdrant retrieval; MCP exposes three authenticated, API-authorised tools. This is still a synthetic-data engineering environment, not a validated clinical product or production deployment. See [Production readiness assessment](docs/PRODUCTION-READINESS.md).

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-MVP%20in%20development-orange.svg)](#roadmap)
[![FHIR](https://img.shields.io/badge/healthcare-HL7%20FHIR%20R4-1b7f79.svg)](https://hl7.org/fhir/R4/)
[![Self-hosted](https://img.shields.io/badge/AI-self--hosted-5b6b8a.svg)](#private-ai-and-mcp)

---

## Contents

- [Overview](#overview)
- [Product principles](#product-principles)
- [MVP capabilities](#mvp-capabilities)
- [Design direction](#design-direction)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Repository structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the platform](#running-the-platform)
- [Snapshots and screenshots](#snapshots-and-screenshots)
- [Synthetic demo data](#synthetic-demo-data)
- [FHIR data model](#fhir-data-model)
- [Digital Twin lifecycle](#digital-twin-lifecycle)
- [Simulation approach](#simulation-approach)
- [Private AI and MCP](#private-ai-and-mcp)
- [Security and privacy](#security-and-privacy)
- [Testing and quality](#testing-and-quality)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Licence](#licence)
- [Disclaimer](#disclaimer)

## Overview

A healthcare Digital Twin is a structured, evolving digital representation of a patient's health state. It is assembled from clinical records and observations over time, with explicit links back to the source data.

twinfixeno aims to make that representation useful and understandable through:

1. **Longitudinal context** — a coherent view of encounters, conditions, medications, observations and reports.
2. **Versioned twin state** — reproducible snapshots of the patient state at a point in time.
3. **Visual exploration** — timelines, trends, completeness indicators and patient-centric views.
4. **Scenario exploration** — transparent, hypothetical calculations against a selected baseline.
5. **Evidence-backed AI** — local language-model assistance grounded in authorised records.
6. **Governed integration** — API-first services and MCP tools with access checks and audit trails.

The initial use case is a synthetic chronic-care patient journey. The MVP is intentionally not a whole-body physiological simulator. The current development environment includes a Keycloak realm and a HAPI FHIR R4 server; patient APIs require a valid Keycloak access token by default.

## Product principles

- **Patient-centred:** the patient twin is the primary workspace.
- **Design-driven:** clinical information should be understandable through visual hierarchy, timelines and trends, not only tables.
- **FHIR-first:** use established healthcare interoperability resources rather than inventing a proprietary clinical format.
- **Source-preserving:** original clinical records are not overwritten by derived twin state.
- **Explainable:** every derived value and AI answer should expose its source, timestamp and relevant assumptions.
- **Private by default:** inference is self-hosted; no external commercial LLM API is required.
- **Human accountable:** AI and simulations support exploration; clinicians retain responsibility for clinical decisions.
- **Modular, not over-engineered:** begin with a modular application and independently containerised supporting services. Introduce distributed orchestration only when justified.

## MVP capabilities

| Capability | MVP scope | Priority |
|---|---|---:|
| Identity and access | Login, roles and patient-level authorisation | Implemented for MVP |
| Patient registry | Search, view and administrator create of synthetic patients | Implemented (synthetic MVP) |
| FHIR integration | Patient sync, local Observation publication, Observation/Condition/Encounter import | Implemented for MVP |
| Twin engine | Immutable snapshots with payload hash and source provenance | Implemented for MVP |
| Clinical timeline | FHIR-backed Observation, Condition and Encounter timeline | Implemented for MVP |
| Twin visualisation | Patient summary and latest observations | Basic MVP |
| Simulation studio | Persisted percentage-delta scenario with explicit assumptions | Implemented (not a clinical model) |
| Audit | Application events for patient access and key mutations | Basic MVP |
| Private AI copilot | Local Ollama LLM with patient-scoped retrieval and source evidence | Implemented for synthetic-data MVP; not clinically validated |
| Evidence assistant | Local RAG question answering plus deterministic fallback report | Implemented for synthetic-data MVP |
| MCP server | Streamable HTTP with timeline, indexing and evidence-query tools; caller token forwarded to API | Implemented for MVP; only three tools |
| Observability | Structured logs, metrics and distributed traces | Not implemented |

### Intended user journey

1. A user signs in and is authorised for a synthetic patient.
2. The application imports or creates FHIR-compatible clinical resources.
3. The twin engine creates a versioned snapshot from the available records.
4. The user explores the patient's clinical timeline and trends.
5. The user creates a hypothetical scenario from a selected baseline.
6. The simulation engine returns a transparent result with assumptions and formula version.
7. The local AI copilot answers questions using permitted records and links its answer to evidence.
8. Relevant actions are recorded for audit and review.

## Design direction

The product should feel like a modern clinical intelligence workspace, not a conventional hospital administration system.

### Primary screens

| Screen | Purpose | Key elements |
|---|---|---|
| Healthcare Command Centre | Overview of the environment | Patient twins, review queue, data quality, recent activity |
| Patient Registry | Find and manage patients | Search, filters, patient summary |
| Patient Digital Twin | Main patient workspace | Patient context, visual health state, trends, evidence panel |
| Clinical Timeline | Explore longitudinal records | Encounters, observations, diagnoses, medications, reports |
| Simulation Studio | Explore hypothetical scenarios | Baseline selector, assumptions, inputs, comparison charts |
| AI Copilot | Ask evidence-grounded questions | Conversation, source citations, model and prompt metadata |
| Governance & Observability | Review platform activity | Audit events, traces, model versions, MCP calls |

### UX principles

- Keep patient identity and selected context visible.
- Clearly distinguish source facts, calculated metrics, AI-generated summaries and hypothetical scenario outputs.
- Display the source timestamp and the time the twin was last calculated.
- Show missing, stale or conflicting data instead of silently filling gaps.
- Use accessible contrast, keyboard navigation and responsive layouts.
- Never communicate a hypothetical simulation as a clinical prediction.

### Screenshot convention

Store approved product screenshots in `docs/screenshots/`. Use descriptive names such as:

- `command-centre.png`
- `patient-digital-twin.png`
- `clinical-timeline.png`
- `simulation-studio.png`
- `ai-copilot.png`
- `governance-observability.png`

Screenshots must use synthetic data only. Do not commit real patient records, names, identifiers, faces or screenshots from production clinical systems.

## Architecture

### Logical architecture

```mermaid
flowchart TB
    U[Clinician / Research User] --> WEB[Next.js Web Workspace]
    WEB -->|OIDC PKCE| IDP[Keycloak]
    WEB -->|Browser API requests| GW[Apache APISIX]
    GW --> API[FastAPI Application API]
    API --> PG[(PostgreSQL)]
    API --> FHIR[HAPI FHIR R4]
    API --> VDB[(Qdrant)]
    API --> LLM[Ollama: Qwen 2.5 3B]
    API --> EMB[Ollama: nomic-embed-text]
    MCP[MCP Streamable HTTP] -->|Forwards caller bearer token| API
    API --> AUDIT[Application Audit Events]
    API --> TWIN[Snapshot / Timeline / Simulation Modules]
```

The browser uses the APISIX gateway at `http://localhost:9080` for API requests. The direct FastAPI port at `http://localhost:8000` is retained for local OpenAPI and diagnostics. Keycloak is reached by the browser at `http://localhost:8081`; the API validates tokens using its internal Keycloak JWKS URL.

### Deployment topology

The MVP is designed for a single developer workstation or private server using Docker Compose. Each major runtime component runs in a container, while the application code remains organised as a monorepo.

Kubernetes is deliberately out of scope for the first milestone. It can be introduced later for multi-node scheduling, high availability and larger deployments.

### Architectural boundaries

- The **FHIR server** manages interoperable clinical resources.
- **PostgreSQL** is the application system of record for twin metadata, application entities, snapshots and audit metadata.
- The **Twin Engine** creates derived state; it does not replace source clinical records.
- The **Simulation Engine** runs deterministic, versioned calculations.
- The **AI Orchestrator** coordinates retrieval and model interactions.
- The **MCP Server** exposes narrowly scoped capabilities and reuses backend authorisation.
- **APISIX** is the north-south API gateway; it does not replace service-level authorisation.
- **Keycloak** provides identity and token issuance; application services still enforce resource permissions.

## Technology stack

The table distinguishes components actually present in the current Compose stack from future architecture options. Do not infer that a proposed technology is deployed merely because it appears in an architectural discussion.

| Layer | Implemented component | Current responsibility / status |
|---|---|---|
| Web | Next.js 15, React 19, TypeScript | Patient workspace and runtime-configured API/OIDC |
| API | FastAPI, Pydantic, SQLAlchemy | Patient, access, FHIR, snapshot, simulation, audit and RAG routes |
| Identity | Keycloak 26.1.4, OIDC PKCE, JWT/JWKS validation | Development realm, roles and browser login |
| Primary database | PostgreSQL 16 | Patient, grants, FHIR index, snapshots, simulations and audit metadata |
| Healthcare interoperability | HAPI FHIR 7.4, FHIR R4 | Patient upsert, Observation publication and Observation/Condition/Encounter import |
| API gateway | Apache APISIX 3.9.1 | Browser API routing to FastAPI |
| Local inference | Ollama 0.6.8 | Local chat and embeddings |
| Chat model | Qwen 2.5 3B | Local evidence-answer generation; synthetic-data use only |
| Embeddings | nomic-embed-text | Local embedding generation |
| Vector store | Qdrant 1.13.2 | Patient-filtered retrieval |
| Tool protocol | Python MCP SDK / FastMCP | Timeline, evidence indexing and evidence query tools |
| Containers | Docker Compose | Local bundled development environment |
| Observability | Not yet implemented | No integrated OpenTelemetry/Prometheus/Grafana/Loki stack |
| Clinical simulation | Not yet implemented | Current scenario engine is a bounded percentage-delta calculation, not physiology |
| Database migrations | Not yet implemented | Runtime schema creation remains; Alembic and tested migration paths are required before production |

### Open-source and licence policy

The project intends to use open-source software only. Before adding a dependency or model artifact:

1. Record its exact version and source.
2. Verify the licence of the actual package or model artifact.
3. Check redistribution, attribution and usage conditions.
4. Record dependencies in a Software Bill of Materials (SBOM).
5. Avoid dependencies that require a proprietary hosted API for core functionality.

The intended project licence is Apache License 2.0. This does not automatically change the licences of third-party dependencies or model weights.

## Repository structure

The current repository is a compact monorepo, not the larger target architecture shown in early design drafts:

```text
twinfixeno/
├── .env.example
├── compose.yaml
├── apps/web/                 # Next.js workspace
├── services/api/             # FastAPI domain/API service and tests
├── services/mcp/             # MCP Streamable HTTP server
├── infrastructure/
│   ├── apisix/
│   └── keycloak/
├── docs/
│   ├── MVP-IMPLEMENTATION.md
│   ├── OPERATIONS.md
│   └── PRODUCTION-READINESS.md
└── .github/workflows/        # API, web-build and Compose smoke CI
```

The repository is populated incrementally. See [MVP implementation status](docs/MVP-IMPLEMENTATION.md) for implementation details, API routes, local test instructions and remaining production-hardening work.

## Prerequisites

For the planned local deployment:

- Git
- Docker Desktop with Docker Compose v2, or Podman with compatible Compose support
- 8 GB RAM minimum for the application-only development profile; 16 GB or more recommended when running a local LLM
- Available disk space for containers, database volumes and model weights
- A modern Chromium, Firefox or Safari browser

Optional for running services outside containers:

- Node.js LTS and npm
- Python 3.12 or the version pinned by the backend project
- Ollama, if running inference directly on the host

A GPU is optional. CPU inference can be used for development, but response times will vary significantly by model and hardware.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/roime81/twinfixeno.git
cd twinfixeno
```

### 2. Create the environment file

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Update local development values as required. Change the Keycloak bootstrap administrator password before use. Never commit populated secrets or production credentials.

### 3. Build and start containers

From the repository root, with Docker Desktop or Docker Engine running:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

This starts the application, Keycloak, PostgreSQL, HAPI FHIR, APISIX, Ollama, Qdrant and MCP service as one Compose stack. On the first run, Ollama downloads the chat and embedding models; API and web startup are gated on that model-pull job. The first boot can therefore take several minutes and requires several GB of download/storage.

Check service status:

```bash
docker compose ps
```

Follow logs:

```bash
docker compose logs -f
```

Stop the environment:

```bash
docker compose down
```

Stop and remove development volumes (destructive; this deletes local database and object data):

```bash
docker compose down -v
```

### 4. Sign in

Open http://localhost:3000. The browser redirects to Keycloak. The imported development realm creates a temporary demo user:

- Clinician: `demo.clinician` / `Demo-Only-Change-Me-2026!` (write access to SYN-0001)
- Researcher: `demo.researcher` / `Demo-Research-Change-Me-2026!` (read-only access to SYN-0001)
- Administrator: `demo.admin` / `Demo-Admin-Change-Me-2026!` (all patients and access-grant management)

Keycloak requires a password change on first sign-in. These credentials are for local synthetic-data development only. Change or remove them before sharing the environment.

### 5. Database and demo data

The API container runs the initial Alembic baseline before starting and then seeds a fictional patient, six synthetic observations, and grants for the demo clinician/researcher when `SEED_DEMO_DATA=true` (the local default). Set `SEED_DEMO_DATA=false` in a non-demo environment. Future schema changes must use explicit reviewed Alembic revisions; the baseline migration is not a substitute for a rehearsed production upgrade plan. Keycloak imports the development realm; HAPI FHIR runs as a separate container.

## Configuration

The committed `.env.example` documents the current local configuration. Replace all defaults before any shared or production deployment.

| Variable | Purpose | Example for local development |
|---|---|---|
| `APP_ENV` | Runtime environment | `development` |
| `APP_SECRET_KEY` | Application signing secret | Generate a random secret |
| `DATABASE_URL` | PostgreSQL connection | `postgresql+psycopg://twinfixeno:change-me@postgres:5432/twinfixeno` |
| `FHIR_BASE_URL` | HAPI FHIR endpoint | `http://fhir:8080/fhir` |
| `KEYCLOAK_ISSUER` | Token issuer | `http://localhost:8081/realms/twinfixeno` |
| `KEYCLOAK_JWKS_URL` | Internal signing-key endpoint | `http://keycloak:8080/realms/twinfixeno/protocol/openid-connect/certs` |
| `JWT_AUDIENCE` | API token audience | `twinfixeno-api` |
| `AUTH_REQUIRED` | Require bearer token | `true` |
| `KEYCLOAK_ADMIN_PASSWORD` | Local bootstrap admin password | Change before use |
| `QDRANT_URL` | Qdrant endpoint | `http://qdrant:6333` |
| `OBJECT_STORAGE_ENDPOINT` | Object storage endpoint | `http://seaweedfs:8333` |
| `OIDC_ISSUER_URL` | Keycloak issuer | Local Keycloak realm URL |
| `OIDC_CLIENT_ID` | OIDC client | `twinfixeno-web` |
| `LLM_PROVIDER` | Local inference provider | `ollama` |
| `LLM_BASE_URL` | Inference endpoint | `http://ollama:11434` |
| `LLM_MODEL` | Model identifier | A locally pulled, licence-verified model |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Telemetry collector | Local OTLP endpoint |

Do not expose PostgreSQL, Qdrant, object storage, model inference or internal service ports to an untrusted network.

## Running the platform

For a step-by-step Docker Compose quick start, service URLs, demo roles and troubleshooting, see [docs/OPERATIONS.md](docs/OPERATIONS.md). The default Compose profile is for local synthetic data only; see [docs/PRODUCTION-READINESS.md](docs/PRODUCTION-READINESS.md) before considering any real deployment.

### Local URLs

These are the development endpoints defined by the current `compose.yaml`. Keycloak redirects the browser to sign in; the API's protected routes require the resulting access token.

| Component | Local URL |
|---|---|
| Web workspace | http://localhost:3000 |
| Browser API gateway (used by the web app) | http://localhost:9080 |
| FastAPI / OpenAPI (direct diagnostics) | http://localhost:8000/docs |
| Keycloak | http://localhost:8081 |
| HAPI FHIR R4 | http://localhost:8090/fhir/metadata |
| Ollama API | http://localhost:11434 |
| Qdrant dashboard | http://localhost:6333/dashboard |
| MCP Streamable HTTP | http://localhost:8001/mcp |

### Developer workflow

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

Backend (from the repository root, using a Python virtual environment):

```bash
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install backend dependencies and start the API after its project files are available:

```bash
pip install -e "services/api[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The container workflow is the supported quick start. The API currently validates access tokens against the Keycloak realm JWKS endpoint.

### FHIR integration quick check

After signing in, use **Sync FHIR** on the patient workspace. The API upserts the synthetic Patient, publishes the six local demo observations as FHIR Observation resources, then imports patient-scoped Observation, Condition and Encounter resources. The authenticated API endpoints are:

- `GET /api/v1/integrations/fhir/status`
- `POST /api/v1/patients/{id}/fhir/sync` — upserts Patient, publishes local observations and ingests Observation, Condition and Encounter resources.
- `GET /api/v1/patients/{id}/fhir`
- `GET /api/v1/patients/{id}/timeline`

FHIR resources are matched to the FHIR Patient reference before they are stored. Imported resources retain FHIR version metadata and content hashes. The APISIX gateway exposes these under `http://localhost:9080`; HAPI FHIR is available at `http://localhost:8090/fhir/metadata`.

### Local AI and RAG

The bundled Compose profile starts Ollama and downloads the configured chat model (`qwen2.5:3b`) and embedding model (`nomic-embed-text`). Qdrant stores patient-scoped evidence vectors. In the Evidence Assistant screen:

1. Open **Check local AI status** (the page also checks automatically when opened).
2. Wait for both models and Qdrant to report ready.
3. Select **Index this patient's records** using a write-authorised account.
4. Ask a question about those indexed records. The response includes retrieved source references and hashes.
5. Use the deterministic context report as a non-LLM fallback.

The API endpoints are `GET /api/v1/ai/status`, `POST /api/v1/patients/{id}/rag/index` and `POST /api/v1/patients/{id}/rag/query`. Retrieval is filtered by patient ID, and the MCP server forwards the caller's bearer token so API role and patient-grant checks remain in force. This is an engineering demonstration over synthetic records; prompt instructions and citations do not constitute clinical safety controls.

## Snapshots and screenshots

In twinfixeno, **snapshot** has two meanings. They should not be confused.

### 1. Product UI snapshots

Screenshots of the user interface belong in `docs/screenshots/`. They document the evolving product experience and should always contain synthetic data.

| Snapshot | Description | Status |
|---|---|---|
| Command Centre | Platform overview | Planned |
| Patient Digital Twin | Patient-centric twin workspace | Planned |
| Clinical Timeline | Longitudinal events and observations | Planned |
| Simulation Studio | Baseline and scenario comparison | Planned |
| AI Copilot | Evidence-grounded conversation | Planned |
| Governance | Audit, traces and model metadata | Planned |

When screenshots are available, embed them here using relative paths, for example:

```markdown
![Patient Digital Twin](docs/screenshots/patient-digital-twin.png)
```

### 2. Patient Digital Twin snapshots

A twin snapshot is a versioned, reproducible representation of the derived patient state at a particular point in time.

A snapshot records:

- Snapshot ID, patient reference and version
- Canonical JSON payload of local observations and imported FHIR resources
- Source FHIR logical ids, versions and lastUpdated timestamps
- Per-record SHA-256 hashes and overall payload SHA-256
- Snapshot creation time and creator
- Source-system and observation-time provenance

The current implementation is append-only, with PostgreSQL triggers and ORM mutation guards. A digest is an integrity checksum, not a digital signature.

Snapshots are append-only. Each snapshot stores a canonical JSON payload, SHA-256 digest, creator, capture time and per-source provenance (source system, resource id, FHIR version, lastUpdated and content hash). PostgreSQL triggers reject UPDATE/DELETE on snapshot headers and artifacts; ORM hooks enforce immutability in local SQLite/test use. A new source-data change creates a new snapshot version.

## Synthetic demo data

The MVP must use synthetic patient data only.

The demo dataset should include a small, coherent longitudinal history with:

- A synthetic patient profile
- Several encounters
- Example conditions
- Medication requests
- Vital-sign observations
- Laboratory observations
- A care plan
- Optional synthetic reports

Data should be internally consistent enough to demonstrate timelines, trends, provenance and scenario comparisons. Clearly label all generated records as synthetic.

Do not use real patient data, production database exports or identifiable clinical documents in development, screenshots, tests or public issue reports.

## FHIR data model

The first interoperability scope targets HL7 FHIR R4.

| Resource | Use in twinfixeno |
|---|---|
| Patient | Patient identity and demographics |
| Encounter | Clinical visit and care context |
| Observation | Vital signs and laboratory measurements |
| Condition | Recorded diagnoses and health conditions |
| MedicationRequest | Medication order/request information |
| DiagnosticReport | Report-level diagnostic information |
| CarePlan | Documented care-plan context |
| DocumentReference | Reference to clinical documents |

FHIR resources remain the interoperable source representation. The current API synchronises the synthetic application patient to a FHIR `Patient` resource, then imports patient-scoped `Observation`, `Condition` and `Encounter` resources. Imported resources retain their FHIR logical id, version, last-updated timestamp, status, effective date, full JSON and SHA-256 digest. A patient-reference check is applied before persistence. The timeline API and dashboard render these imported resources chronologically. MedicationRequest, DiagnosticReport, Procedure, AllergyIntolerance and other resource types remain future work.

Patient-level authorisation is applied to FHIR sync and timeline routes. Administrators can create and revoke patient grants. Clinicians can read assigned patients and write only where the grant is `write`; researchers are read-only. The demo clinician has write access to SYN-0001, while the demo researcher has read-only access. Grants are bound to immutable Keycloak subject IDs by default; username-only matching is an explicit local-demo compatibility setting. The implementation must validate resource profiles and terminology assumptions rather than treating every FHIR resource as clinically equivalent.

## Digital Twin lifecycle

The intended lifecycle is:

```mermaid
flowchart TD
    A[Receive or import FHIR resources] --> B[Validate and normalise]
    B --> C[Resolve patient and source references]
    C --> D[Calculate patient state]
    D --> E[Create versioned twin snapshot]
    E --> F[Visualise timeline and trends]
    E --> G[Select baseline for scenario]
    G --> H[Run deterministic simulation]
    H --> I[Store scenario result and assumptions]
    F --> J[Clinician review]
    I --> J
```

### Snapshot states

- **Draft:** calculation is in progress or awaiting validation.
- **Validated:** structural and application-level checks passed.
- **Published:** available for authorised application use.
- **Superseded:** a newer snapshot exists; the historical snapshot remains available.
- **Invalidated:** a documented issue means the snapshot should not be used.

The status and reason for any invalidation must be auditable.

## Simulation approach

The MVP uses deterministic, transparent scenario calculations. It does not attempt to simulate the entire human body or claim to predict clinical outcomes.

Each simulation must include:

- Baseline snapshot ID
- User-defined scenario inputs
- Input units and validation rules
- Formula or model identifier and version
- Calculation timestamp
- Output values and comparison to baseline
- Assumptions and limitations
- Initiating user and review status

Simulation outputs must be visibly labelled **Hypothetical scenario — not a clinical prediction**.

Future physiological or disease-progression models require domain-expert design, independent validation, clinical governance and appropriate regulatory assessment before clinical use.

## Private AI and MCP

### Implemented local evidence workflow

The Compose environment includes Ollama, Qwen 2.5 3B, nomic-embed-text and Qdrant. The API builds evidence chunks from the selected patient's local profile, observations, imported FHIR records and snapshots. Retrieval applies a patient-ID filter; model answers are returned with the retrieved source type, source identifier, relevance score and content hash.

Current API workflow:

- `GET /api/v1/ai/status` — report Ollama, model and Qdrant availability.
- `POST /api/v1/patients/{id}/rag/index` — index authorised patient records (write access required).
- `POST /api/v1/patients/{id}/rag/query` — query the indexed evidence (read access required).

Re-index after importing new FHIR records or creating a new snapshot. The current implementation does not index uploaded PDFs or arbitrary documents, perform clinical coding reconciliation, evaluate answer quality, or preserve complete model/prompt/tool version telemetry. Retrieved evidence and model-generated prose must be reviewed by a qualified human. It must not be used for diagnosis, treatment, triage or clinical decision-making.

### Implemented MCP tools

The MCP Streamable HTTP server is available at `http://localhost:8001/mcp` and currently exposes:

| Tool | Purpose | Access |
|---|---|---|
| `get_patient_timeline` | Read an authorised patient's FHIR timeline | Patient read access |
| `index_patient_evidence` | Index selected patient records into Qdrant | Patient write access |
| `ask_patient_evidence` | Query retrieved evidence for an authorised patient | Patient read access |

The MCP server requires a caller bearer token and forwards it to the FastAPI service. The API remains the enforcement point for Keycloak role and patient-grant checks. MCP is not itself an identity provider or a substitute for API authorisation. The broader proposed tool catalogue is not implemented yet.

### AI safety and traceability gaps

The current system has a bounded prompt and patient-filtered retrieval, but does not yet provide prompt-injection resistance, model evaluation, independent clinical review workflow, model/prompt/tool version registry, full distributed trace correlation, automated hallucination evaluation, or a validated clinical decision-support safety case. Do not treat the assistant as clinical decision support.

## Security and privacy

Security controls are foundational, even in the MVP.

- OIDC authentication through Keycloak (development realm and browser PKCE flow).
- API-side RS256 JWT signature, issuer and audience validation against Keycloak JWKS.
- Patient-level grants bound to Keycloak subject and/or username; unassigned patient lookups return 404.
- Administrators have platform-wide access; clinicians require a write grant for mutations; researchers are read-only.
- Administrator-only access grant creation and revocation.
- Server-side permission checks on every patient resource and MCP tool.
- PostgreSQL row-level security where appropriate, in addition to application checks.
- TLS for network communications in shared environments.
- Encrypted storage and protected backups.
- Secrets excluded from source control.
- Restricted internal service networking.
- Append-only or tamper-evident audit design.
- Prompt, model, retrieval and tool-call traceability.
- No external LLM API in the default architecture.
- Synthetic data for public development and demonstrations.

A production healthcare deployment requires a formal threat model, penetration testing, operational security controls, backup and recovery exercises, clinical safety assessment and applicable regulatory review.

## Testing and quality

The Pytest suite covers patient access isolation, role/grant permissions, registry search/create, scenario persistence, audit events, FHIR ingestion and patient-reference filtering, timeline, snapshot hashes/immutability, and the RAG API's role and patient-access boundaries. The live HAPI test exercises real FHIR publication/import against a containerised HAPI server. GitHub Actions runs API/live-FHIR tests, a Next.js production build and a full Docker Compose smoke deployment. Check the latest Actions run on the current commit; a successful API test or web build alone is not proof that every container or browser workflow works. Run locally from `services/api` with `pip install -r requirements-dev.txt` followed by `pytest -q`; the live HAPI test is skipped unless `FHIR_INTEGRATION_TESTS=1` and `FHIR_BASE_URL` point to a running server. The broader planned quality strategy includes:

| Test type | Coverage |
|---|---|
| Unit | Twin calculations, validation and simulation formulas |
| API integration | Patient, FHIR, snapshot and scenario endpoints |
| Data | Migration, constraints, provenance and access isolation |
| AI | Retrieval relevance, citation presence and refusal/guardrail behaviour |
| MCP | Tool schemas, authorisation and audit events |
| Security | Cross-patient access, token validation and injection boundaries |
| End-to-end | Login through patient exploration and scenario review |
| Operational | Container health checks, logs and recovery behaviour |

Clinical correctness cannot be established by software tests alone. Domain experts must review clinical semantics and any future clinical model.

## Roadmap

### Milestone 0 — Repository and design foundation
- [x] Project name and repository established
- [x] Product README and architecture description
- [ ] Separate approved product requirements and design specification documents
- [x] Responsive application shell and initial design styling

### Milestone 1 — Platform foundation
- [x] Next.js application shell and container build
- [x] FastAPI service and container build
- [x] PostgreSQL persistence
- [ ] Formal Alembic database migrations and rollback verification
- [x] Keycloak authentication (development OIDC and API token validation)
- [x] Patient-level access grants, effective permission endpoint and admin governance UI
- [x] APISIX gateway
- [x] Docker Compose integrated local environment with readiness checks

### Milestone 2 — Patient and twin
- [x] Synthetic patient registry: authorised list, search and admin creation
- [x] HAPI FHIR Patient synchronisation
- [x] FHIR Observation publication and Observation/Condition/Encounter ingestion
- [x] Twin snapshot payload, hash and source provenance
- [x] Immutable versioned snapshot artifacts and UI inspection
- [x] FHIR-backed clinical timeline
- [x] Patient overview and latest observation visualisation

### Milestone 3 — Simulation
- [x] Scenario data model and persisted runs
- [x] Deterministic percentage-delta calculation engine
- [x] Baseline versus projected value comparison
- [x] Scenario inputs, formula ID, assumptions and timestamp provenance
- [x] Simulation Studio UI
- [ ] Clinically validated physiological models and clinical governance

### Milestone 4 — Private AI and MCP
- [x] Local Ollama model runtime with Qwen 2.5 3B and nomic-embed-text
- [x] Patient-scoped RAG retrieval and source references
- [x] Local evidence-grounded LLM responses with bounded prompt and synthetic-data disclaimer
- [x] MCP Streamable HTTP server with three API-authorised tools
- [ ] AI, prompt, model and tool-call audit/version management
- [x] Local deterministic patient context summary (not an LLM)

### Milestone 5 — Hardening and demonstration
- [ ] Dedicated OpenTelemetry / Prometheus / Grafana / centralised logging stack
- [x] Automated API integration tests, live HAPI FHIR CI and RAG access-boundary tests
- [x] Next.js production build in CI
- [x] Docker Compose configuration/build/start smoke workflow
- [ ] Full browser E2E, security and recovery tests
- [x] Synthetic seed patient and observations
- [ ] Approved UI screenshots
- [x] Local deployment and production-readiness documentation
- [ ] Production identity, TLS, migrations, backup/restore, security and clinical sign-off

## Contributing

Contributions are welcome. Before implementation begins, please open an issue to discuss significant architecture or clinical-domain changes.

Expected contribution practices:

1. Keep changes focused and documented.
2. Add tests for new behaviour.
3. Do not include real patient data.
4. Document new environment variables.
5. Pin dependencies and review licences.
6. Preserve auditability and patient-level access controls.
7. Never describe an unvalidated feature as clinically safe or effective.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and [SECURITY.md](SECURITY.md) for vulnerability reporting and sensitive-data handling.

## Licence

This repository is distributed under the **Apache License 2.0**; see [LICENSE](LICENSE). Third-party dependencies, model weights and datasets retain their own licences and terms.

## Disclaimer

twinfixeno is an early-stage open-source engineering project for research, prototyping and software development. It is not a medical device, is not validated for diagnosis or treatment, and must not be used to make or automate clinical decisions.

Use synthetic data only unless and until the platform has undergone the necessary legal, privacy, security, clinical validation and regulatory processes for a specific deployment.

---

**Repository:** https://github.com/roime81/twinfixeno  
**Project:** twinfixeno — Healthcare Digital Twin Platform

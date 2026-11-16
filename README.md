# TWINFixeno

**An open-source, privacy-first healthcare Digital Twin platform.**

twinfixeno is an early-stage, design-driven MVP for creating a longitudinal digital representation of a patient's health journey. It brings together interoperable clinical data, versioned patient-state snapshots, explainable analytics, hypothetical scenario exploration, private local language models and governed Model Context Protocol (MCP) tools.

> **Project status:** Early MVP implementation. The repository includes a runnable Next.js + FastAPI + PostgreSQL + APISIX foundation. Authentication, FHIR integration, simulation, AI/MCP and full observability remain planned.

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

The initial use case is a synthetic chronic-care patient journey. The MVP is intentionally not a whole-body physiological simulator.

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
| Identity and access | Login, roles and patient-level authorisation | P0 |
| Patient registry | Create, search and view synthetic patients | P0 |
| FHIR integration | Import and retrieve selected FHIR R4 resources | P0 |
| Twin engine | Aggregate, calculate and version patient snapshots | P0 |
| Clinical timeline | Encounters, conditions, medications and observations | P0 |
| Twin visualisation | Patient summary, trends and data completeness | P0 |
| Simulation studio | Baseline versus clearly labelled hypothetical scenario | P0 |
| Audit | User, data access, AI and tool invocation events | P0 |
| Private AI copilot | Local LLM with patient-scoped retrieval and citations | P1 |
| MCP server | Governed read and simulation tools | P1 |
| Observability | Structured logs, metrics and distributed traces | P1 |

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
    U[Clinician / Research User] --> WEB[Next.js Web Application]
    WEB --> GW[Apache APISIX API Gateway]

    GW --> API[FastAPI Application API]
    API --> IDP[Keycloak OIDC]
    API --> FHIR[HAPI FHIR R4]
    API --> TWIN[Digital Twin Engine]
    API --> SIM[Simulation Engine]
    API --> AUDIT[Audit Service]

    TWIN --> PG[(PostgreSQL)]
    SIM --> PG
    API --> OBJ[(SeaweedFS Object Storage)]
    API --> VDB[(Qdrant Vector Database)]
    FHIR --> PG

    WEB --> AI[AI Orchestrator / LangGraph]
    AI --> LLM[Local LLM: Ollama or vLLM]
    AI --> RET[RAG Retrieval]
    RET --> VDB
    AI --> MCP[MCP Server]
    MCP --> API

    API --> OTEL[OpenTelemetry]
    AI --> OTEL
    MCP --> OTEL
    OTEL --> OBS[Prometheus / Grafana / Loki]
```

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

The project favours mature, self-hostable open-source components. Exact versions should be pinned in deployment manifests and lockfiles as implementation begins.

| Layer | Proposed technology | Responsibility |
|---|---|---|
| Web framework | Next.js, React, TypeScript | Application shell and user experience |
| UI system | Tailwind CSS, shadcn/ui | Design system and reusable components |
| Visualisation | Apache ECharts | Clinical trends and scenario comparisons |
| Graph/workflow UI | React Flow | Optional relationship and workflow views |
| API/backend | Python, FastAPI, Pydantic | REST APIs and domain services |
| ORM/migrations | SQLAlchemy, Alembic | Persistence and schema evolution |
| Primary database | PostgreSQL | Transactional application data and snapshots |
| Healthcare standard | HL7 FHIR R4 | Clinical interoperability |
| FHIR server | HAPI FHIR | FHIR API and resource persistence |
| API gateway | Apache APISIX | Routing, rate limits and gateway policies |
| Identity | Keycloak | OIDC authentication and role claims |
| Vector database | Qdrant | Embedding storage and semantic retrieval |
| Object storage | SeaweedFS | Clinical document and object storage |
| AI orchestration | LangGraph | Explicit, stateful AI workflows |
| Local inference | Ollama (development), vLLM (serving) | Private model inference |
| Initial model | Qwen family model, licence verified per artifact | Local language-model capability |
| Agent protocol | MCP Python SDK | Governed tool integration |
| Background work | Python worker; queue selected during implementation | Asynchronous processing |
| Containers | Docker Compose / Podman | Local and private deployment |
| Telemetry | OpenTelemetry | Traces, metrics and instrumentation |
| Metrics | Prometheus | Metrics collection |
| Dashboards | Grafana | Operational dashboards |
| Logs | Loki | Centralised application logs |
| Tests | Pytest, Vitest, Playwright | Backend, frontend and end-to-end tests |

### Open-source and licence policy

The project intends to use open-source software only. Before adding a dependency or model artifact:

1. Record its exact version and source.
2. Verify the licence of the actual package or model artifact.
3. Check redistribution, attribution and usage conditions.
4. Record dependencies in a Software Bill of Materials (SBOM).
5. Avoid dependencies that require a proprietary hosted API for core functionality.

The intended project licence is Apache License 2.0. This does not automatically change the licences of third-party dependencies or model weights.

## Repository structure

The target monorepo layout is:

```text
twinfixeno/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── .env.example
├── .gitignore
├── compose.yaml
├── docs/
│   ├── PRODUCT-VISION.md
│   ├── REQUIREMENTS.md
│   ├── TECHNICAL-ARCHITECTURE.md
│   ├── UI-UX-SPECIFICATION.md
│   ├── DATA-MODEL.md
│   ├── API-SPECIFICATION.md
│   ├── AI-MCP-SPECIFICATION.md
│   ├── SECURITY-GOVERNANCE.md
│   ├── MVP-ROADMAP.md
│   └── screenshots/
├── apps/
│   └── web/
├── services/
│   ├── api/
│   ├── patient-service/
│   ├── twin-engine/
│   ├── simulation-engine/
│   ├── ai-orchestrator/
│   ├── mcp-server/
│   └── worker/
├── database/
│   ├── migrations/
│   ├── schemas/
│   └── seed/
├── infrastructure/
│   ├── apisix/
│   ├── keycloak/
│   ├── fhir/
│   ├── observability/
│   └── containers/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── e2e/
└── .github/
    └── workflows/
```

The repository is populated incrementally. See [MVP implementation status](docs/MVP-IMPLEMENTATION.md) for implemented and planned components.

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

Update local development values as required. Never commit populated secrets or production credentials.

### 3. Build and start containers

From the repository root, with Docker Desktop or Docker Engine running:

```bash
docker compose pull
docker compose build
docker compose up -d
```

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

### 4. Initialise the database

Formal Alembic migrations are a follow-up; the current API creates its initial schema on startup. The planned migration command is:

```bash
docker compose exec api alembic upgrade head
```

Synthetic demo data will be loaded through a dedicated seed command once the seed utility is implemented.

> **Current status:** The Docker Compose foundation is committed. Keycloak, HAPI FHIR, migrations, simulation and AI services are not yet included; consult `docs/MVP-IMPLEMENTATION.md`.

## Configuration

The planned `.env.example` will document configuration similar to the following. Use generated local-only values and replace all defaults before any shared or production deployment.

| Variable | Purpose | Example for local development |
|---|---|---|
| `APP_ENV` | Runtime environment | `development` |
| `APP_SECRET_KEY` | Application signing secret | Generate a random secret |
| `DATABASE_URL` | PostgreSQL connection | `postgresql+psycopg://twinfixeno:change-me@postgres:5432/twinfixeno` |
| `FHIR_BASE_URL` | HAPI FHIR endpoint | `http://hapi-fhir:8080/fhir` |
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

### Planned local URLs

These are the development endpoints defined by the current `compose.yaml`.

| Component | Proposed URL |
|---|---|
| Web application | http://localhost:3000 |
| FastAPI / OpenAPI | http://localhost:8000/docs |
| APISIX gateway | http://localhost:9080 |
| HAPI FHIR | http://localhost:8080/fhir |
| Keycloak | http://localhost:8081 |
| Qdrant dashboard/API | http://localhost:6333/dashboard |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |

### Planned developer workflow

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

The current container workflow is the supported quick start. The standalone developer commands are retained for the next development iteration.

### Local LLM

For a host-based Ollama development setup, install Ollama using its official installation instructions, then pull a model whose exact artifact licence has been reviewed.

```bash
ollama pull <verified-model-name>
ollama list
```

The model name is deliberately not hard-coded here: model tags and licences must be verified before use. In container deployments, ensure the inference service is reachable only from authorised internal services.

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

A snapshot should record:

- Snapshot ID and patient reference
- Source FHIR resource references and versions
- Clinical observation time range
- Snapshot creation time
- Twin engine and calculation version
- Normalised measurements and derived metrics
- Data completeness and validation status
- Provenance and calculation metadata

Snapshots must be immutable once finalised. A new source-data change or engine version creates a new snapshot rather than silently rewriting history.

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

FHIR resources remain the interoperable source representation. The twin engine creates application-specific derived state with references back to those resources.

The implementation must validate resource profiles and terminology assumptions rather than treating every FHIR resource as clinically equivalent.

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

### AI workflow

The planned AI workflow is:

1. Authenticate the user and resolve the authorised patient context.
2. Retrieve only records the user is permitted to access.
3. Build a bounded, patient-scoped context.
4. Retrieve relevant evidence from structured records and approved documents.
5. Invoke the local LLM through the AI orchestrator.
6. Return an answer with source references and timestamps.
7. Record model, prompt, retrieval and tool metadata in the audit trail.

The LLM must not invent missing records, silently infer diagnoses or convert hypothetical simulation outputs into clinical recommendations.

### Initial MCP tools

| Tool | Purpose | Access |
|---|---|---|
| `get_patient_summary` | Retrieve an authorised patient summary | Read |
| `get_patient_timeline` | Retrieve longitudinal events | Read |
| `get_observations` | Retrieve selected observations | Read |
| `get_twin_snapshot` | Retrieve a twin snapshot | Read |
| `create_scenario` | Create a hypothetical scenario | Controlled write |
| `run_simulation` | Run an approved deterministic simulation | Controlled execution |
| `compare_scenarios` | Compare scenario outputs | Read |
| `get_evidence` | Retrieve source references | Read |

MCP is a protocol boundary, not an authorisation mechanism. Every tool must validate identity, patient scope, permission, input schema and audit requirements. Tool execution must not rely solely on instructions supplied to the LLM.

## Security and privacy

Security controls are foundational, even in the MVP.

- OIDC authentication through Keycloak.
- Role-based access and patient-level authorisation.
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

The planned quality strategy includes:

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
- [x] Initial product README
- [ ] Product requirements and architecture documents
- [ ] Design tokens and application shell

### Milestone 1 — Platform foundation
- [x] Next.js application shell
- [x] FastAPI service
- [x] PostgreSQL persistence
- [ ] Formal database migrations
- [ ] Keycloak authentication
- [x] APISIX gateway
- [x] Docker Compose development environment

### Milestone 2 — Patient and twin
- [ ] Synthetic patient registry
- [ ] HAPI FHIR integration
- [ ] FHIR resource ingestion
- [ ] Twin state generation
- [ ] Immutable versioned snapshots
- [ ] Clinical timeline and trends

### Milestone 3 — Simulation
- [ ] Scenario data model
- [ ] Deterministic simulation engine
- [ ] Baseline comparison
- [ ] Scenario provenance and versioning
- [ ] Simulation Studio UI

### Milestone 4 — Private AI and MCP
- [ ] Local model runtime
- [ ] Patient-scoped RAG
- [ ] Evidence-linked answers
- [ ] MCP server and governed tools
- [ ] AI and tool-call audit trail

### Milestone 5 — Hardening and demonstration
- [ ] Observability dashboards
- [ ] Automated security and integration tests
- [ ] Synthetic demo dataset
- [ ] UI screenshots
- [ ] Deployment and operator documentation

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

Contribution guidelines and a code of conduct will be added as the project matures.

## Licence

The intended project licence is **Apache License 2.0**. A `LICENSE` file must be added to the repository before the licence is considered formally applied. Third-party dependencies, model weights and datasets retain their own licences and terms.

## Disclaimer

twinfixeno is an early-stage open-source engineering project for research, prototyping and software development. It is not a medical device, is not validated for diagnosis or treatment, and must not be used to make or automate clinical decisions.

Use synthetic data only unless and until the platform has undergone the necessary legal, privacy, security, clinical validation and regulatory processes for a specific deployment.

---

**Repository:** https://github.com/roime81/twinfixeno  
**Project:** twinfixeno — Healthcare Digital Twin Platform

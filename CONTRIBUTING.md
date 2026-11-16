# Contributing to twinfixeno

Thank you for considering a contribution.

## Scope and safety

- Use synthetic or de-identified test fixtures only. Never commit identifiable patient data, screenshots, database dumps, tokens, passwords or private keys.
- Do not describe a feature as clinically validated unless the evidence and formal review are documented.
- The project is an engineering prototype, not a medical device or clinical decision-support product.
- Keep patient-level authorisation enforced by the FastAPI service. The UI and MCP layer are not security boundaries.

## Development workflow

1. Create a branch from `main`.
2. Make a focused change and update relevant documentation.
3. Add or update API tests for new backend behaviour.
4. Run API tests from `services/api`:
   ```bash
   pip install -r requirements-dev.txt
   pytest -q
   ```
5. Run the web production build:
   ```bash
   cd apps/web
   npm install
   npm run build
   ```
6. Validate the bundled environment from the repository root:
   ```bash
   docker compose config --quiet
   docker compose up --build -d
   docker compose ps
   ```
7. Open a pull request with a concise summary, test evidence, configuration changes and known limitations.

## Engineering expectations

- Keep API contracts documented and backwards-compatible where practical.
- Validate all patient identifiers and enforce patient-level access for each operation.
- Record source provenance for imported or derived clinical data.
- Keep snapshots and audit events append-only.
- Do not log bearer tokens, secrets or clinical payloads unnecessarily.
- Pin container images and application dependencies; review licences before adding models or packages.
- Include recovery and migration considerations for persistence changes.

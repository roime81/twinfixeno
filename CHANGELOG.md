# Changelog

All notable changes to TwinFixeno are documented here.

## Unreleased

### Added
- LiteLLM as a provider-neutral chat completion adapter for the existing Evidence Assistant.
- Configuration-based provider selection for local Ollama/Qwen, OpenAI, Anthropic, Google Gemini and OpenAI-compatible endpoints.
- Provider setup and healthcare data-handling guidance in [LLM provider configuration](docs/LLM-PROVIDERS.md).
- Automated unit coverage for LiteLLM request routing and response normalisation.

### Changed
- Evidence Assistant chat generation now uses LiteLLM while keeping Ollama as the default local provider.
- AI status metadata reports the configured chat provider and model.
- GitHub Actions now explicitly runs the LiteLLM adapter tests and triggers for provider documentation and changelog changes.

### Unchanged
- Ollama remains responsible for local embeddings.
- Qdrant patient-filtered retrieval, prompts, patient authorisation, API routes, MCP tools, Keycloak, UI and Compose topology remain unchanged.
- No external provider is enabled by default; credentials remain server-side configuration.

### Safety
- External LLMs must not receive real patient data or PHI until the provider, contractual terms, jurisdiction, privacy controls and processing purpose are reviewed and approved.
- This remains a synthetic-data engineering MVP, not a clinically validated product.

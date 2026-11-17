# LLM provider configuration

TwinFixeno uses LiteLLM for chat completion while preserving its existing RAG and data-access flow.

## Default behaviour

The default configuration remains local and private:

- Chat: LiteLLM `ollama_chat/qwen2.5:3b` → local Ollama.
- Embeddings: local Ollama `nomic-embed-text`.
- Retrieval: existing patient-filtered Qdrant collection.
- Authorisation, audit, API routes and MCP tools: unchanged.

LiteLLM is used as a Python SDK inside the existing FastAPI service. No additional gateway container, database, UI or network-facing port is introduced.

## Configure another provider

Edit the local `.env` file. Do not commit API keys.

### OpenAI

```dotenv
LLM_MODEL=openai/<provider-model-id>
LLM_API_BASE=
LLM_API_KEY=
OPENAI_API_KEY=<secret>
```

Alternatively, put the key in `LLM_API_KEY` and leave `OPENAI_API_KEY` unset.

### Anthropic

```dotenv
LLM_MODEL=anthropic/<provider-model-id>
LLM_API_BASE=
ANTHROPIC_API_KEY=<secret>
```

### Google Gemini

```dotenv
LLM_MODEL=gemini/<provider-model-id>
LLM_API_BASE=
GEMINI_API_KEY=<secret>
```

### OpenAI-compatible endpoint

```dotenv
LLM_MODEL=openai/<provider-model-id>
LLM_API_BASE=https://<provider-host>/v1
LLM_API_KEY=<secret>
```

Use the provider's exact model identifier and current LiteLLM provider prefix. Restart the API after changing provider settings.

## Operational notes

- Ollama remains required for embeddings, even when chat uses an external provider.
- The configured chat model and provider are reported by `GET /api/v1/ai/status`.
- External providers are not selected by default. A provider is used only after an operator changes `LLM_MODEL` and supplies the required credentials.
- Provider selection is deployment configuration, not a user-facing runtime switch. A provider administration UI is intentionally out of scope for this change.
- Never put API keys in source control, frontend configuration, logs or audit event details.
- The current project is a synthetic-data engineering MVP. Do not send real patient data or PHI to an external model unless the provider, contract, jurisdiction, privacy/security controls and data-processing purpose have been formally reviewed and approved.
- LiteLLM normalises the chat API; it does not guarantee identical model capabilities, clinical quality, tool calling or context limits across providers.

This change does not modify embeddings, Qdrant indexing, patient-level retrieval filters, prompts, API routes, LangGraph/MCP services, Keycloak authorisation or the web UI.

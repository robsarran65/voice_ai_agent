# MunAI Voice AI Agent — Multi-Tenant Production Scaffold

Purpose: a configurable SaaS codebase that preserves the demo's low-cost behavior while making tenant-specific behavior easy to manage.

## Tenant configuration

Edit `config/tenants.json`. Each tenant can configure:

- assistant name
- company name
- primary and fallback models
- output-token ceiling
- temperature
- phone-history window and compaction size
- monthly LLM budget target
- enabled capabilities: weather, calendar, email
- trusted caller numbers
- Vapi assistant IDs

The configuration loader hot-reloads the JSON file when it changes. Set `MUNAI_TENANT_CONFIG` to use a different path and `MUNAI_DEFAULT_TENANT` to choose the default tenant.

## Tenant routing

For browser/API traffic, send:

```text
X-MunAI-Tenant: munai-demo
```

or include `tenant_id` in the `/voice-chat/` request body.

For Vapi, the phone route can resolve a tenant from `X-MunAI-Tenant` or from a configured Vapi assistant ID.

## Cost controls implemented

- GPT-5 nano is the default model
- deterministic zero-token fast paths
- bounded phone history with no summary-model call
- direct weather response after the tool result, avoiding a second LLM call
- OpenAI prompt-cache key per tenant
- per-call token, cached-token, cost, latency and fallback telemetry
- per-tenant max output tokens
- per-tenant capability switches
- tenant-scoped caller allowlists

## Production hardening still required before regulated/customer-private workloads

This package is a production-oriented scaffold, but several shared-state items from the original project remain process-local or globally scoped. Before handling multiple customers' private Google data in production, move pending confirmations to a shared store and make Google OAuth credentials/token storage tenant-scoped. A persistent cost ledger should also back the configured monthly budget if hard enforcement is required.

Recommended next infrastructure additions, only when needed:

1. Postgres for tenants, usage ledger, audit metadata, and OAuth references.
2. Redis or another short-lived shared store for pending confirmations and session state.
3. Secret manager for tenant credentials.
4. Centralized observability for cost, latency, errors, and model fallback rates.

Do not add a vector database unless a concrete retrieval use case requires it.

## Vercel demo secrets

For the hosted MunAI demo, use `GOOGLE_TOKEN_JSON_B64` rather than shipping `api/.secrets/token.json`. The Google credential loader supports either the local file (development) or the environment token (serverless). Gmail remains read-only in the demo.

Live web search uses the OpenAI Responses API built-in web search tool and requires only `OPENAI_API_KEY`.

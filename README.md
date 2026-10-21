# LCL — AI configuration (Helm chart)

Demo content for a Kong AI Gateway 2.x lab on Kong Operator: the bank, entities and host names
are illustrative.

`chart/` is LCL's chart, `lcl-aigw`: what LCL's AI team owns on its AI Gateway. The team
chooses its providers, endpoints, MCP upstreams and token budgets; changes are reviewed in this repo.

| Template | What |
|---|---|
| `10-providers.yaml` | model providers (Gemini, Vertex AI through PSC, OpenAI, on-prem); keys are `secretRef`s to `entity-credentials` |
| `20-policies.yaml` | consumer groups (= ADFS groups) and AI policies: prompts, guardrails, PII, semantic cache, usage plan |
| `30-models.yaml` | AI Models: what clients call, which targets, which policies |
| `40-mcp.yaml` | an MCP server exposing a REST API as tools |

`lab/backends/` holds lab stand-ins for LCL's backends, outside the chart: Redis (usage-plan
counters), pgvector (semantic guard and cache), Ollama (on-prem model), mock-vertex (Claude on
Vertex through PSC), the agences API (MCP tools), the PII service, and a cert-manager lab CA for the
gateway and mock-vertex certificates. Apply them with `kubectl` before the chart syncs; replace them
with LCL's real services in production.

The Argo CD Application `lcl-aigw` syncs it into namespace `ai-gateway` as the ServiceAccount
`argocd/entity-deployer`. CAGIP's platform chart
([cagip-aigw-platform-gitops](https://github.com/bcollard/cagip-aigw-platform-gitops)) decides what that identity may do:

- RBAC: these five kinds only, in that namespace only.
- ValidatingAdmissionPolicies: every Model lists the ADFS auth strategy and the mandatory
  policies `cagip-strip-identity` and `cagip-baseline-guard`; policy types from CAGIP's list; no
  LLM endpoint the group denies; usage plans on Redis with a total budget; no Lua, no global
  policy, no inline key.

Not in Git: the Secret `entity-credentials` (`GEMINI_API_KEY`, `OPENAI_BEARER`, `VERTEX_SA_JSON`,
`PGVECTOR_PASSWORD`), created out of band by LCL. Policies read its keys as
`{vault://env/entity-<key>}`.

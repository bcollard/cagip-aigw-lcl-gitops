# LCL — AI configuration (Helm chart)

Demo content for a Kong AI Gateway 2.x lab on Kong Operator: the bank, entities and host names
are illustrative.

`chart/` is LCL's chart, `lcl-aigw`: what LCL's AI team owns on its AI Gateway.

| Template | What |
|---|---|
| `10-providers.yaml` | model providers (Gemini, Vertex AI through PSC, OpenAI, on-prem); keys are `secretRef`s to `entity-credentials` |
| `20-policies.yaml` | consumer groups (= ADFS groups) and AI policies: prompts, guardrails, PII, semantic cache, usage plan |
| `30-models.yaml` | AI Models: what clients call, which targets, which policies |
| `40-mcp.yaml` | an MCP server exposing a REST API as tools |

The Argo CD Application `lcl-aigw` syncs it into namespace `ai-gateway` as the ServiceAccount
`argocd/entity-deployer`. CAGIP's platform chart
([cagip-aigw-platform-gitops](https://github.com/bcollard/cagip-aigw-platform-gitops)) decides what that identity may do:

- RBAC: these five kinds only, in that namespace only.
- ValidatingAdmissionPolicies: every Model lists the ADFS auth strategy and the mandatory
  policies `cagip-strip-identity` and `cagip-baseline-guard`; policy and provider types, upstream
  hosts and the token cap come from CAGIP's values; no Lua, no global policy, no inline key.

Not in Git: the Secret `entity-credentials` (`GEMINI_API_KEY`, `OPENAI_BEARER`, `VERTEX_SA_JSON`,
`PGVECTOR_PASSWORD`), created out of band by LCL. Policies read its keys as
`{vault://env/entity-<key>}`.

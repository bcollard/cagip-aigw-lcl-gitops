# LCL — AI Gateway GitOps

Synced by the Argo CD Application `lcl-aigw` (project `lcl`), impersonating `lcl:lcl-gitops`:
every object goes through the CAGIP RBAC and ValidatingAdmissionPolicies. Demo content for a
Kong AI Gateway 2.x lab on Kong Operator.

| File | What |
|---|---|
| `10-providers.yaml` | the entity's model providers; keys are `secretRef`s to `lcl-llm-keys` |
| `20-policies.yaml` | consumer groups and AI policies (quotas, guards, cache, prompts, log tags) |
| `30-models.yaml` | AI Models: what clients call, which targets, which policies |
| `40-mcp.yaml` | MCP server exposing a REST API as tools |

Not in Git: `lcl-llm-keys`, written by the entity's pipeline (write-only: no entity identity can
read Secrets in the namespace).

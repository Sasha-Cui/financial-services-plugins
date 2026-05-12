# Local vs Upstream Gap Analysis

Date: May 12, 2026

## Scope

This report compares:

- Local repo: `/Users/cui/Documents/GitHub/financial-services-plugins`
- Upstream reference: `anthropics/financial-services`, inspected on May 12, 2026

The comparison focuses on repository structure, plugin surface area, skill coverage, and packaging model.

## Top-Level Structure

| Category | Local repo | Upstream repo | Gap |
| --- | --- | --- | --- |
| Marketplace name | `financial-services-plugins` | `claude-for-financial-services` | Naming and positioning diverged |
| Vertical plugin folders | Flat at repo root | Nested under `plugins/vertical-plugins/` | Structural divergence |
| Agent plugin folders | None | `plugins/agent-plugins/` | Missing |
| Managed-agent cookbooks | None | `managed-agent-cookbooks/` | Missing |
| Microsoft 365 installer | None | `claude-for-msft-365-install/` | Missing |
| Shared connector ownership | `financial-analysis/.mcp.json` | `plugins/vertical-plugins/financial-analysis/.mcp.json` | Equivalent |

## Inventory Comparison

| Metric | Local repo | Upstream repo |
| --- | ---: | ---: |
| Vertical plugins | 5 | 7 |
| Agent plugins | 0 | 10 |
| Partner-built plugins | 2 | 2 |
| Total commands | 47 | 47 |
| Total skills | 53 | 117 |
| Shared connectors | 11 | 11 |

## Vertical Coverage

| Workflow area | Local status | Upstream status | Notes |
| --- | --- | --- | --- |
| Financial analysis | Present | Present | Local version is thinner on background skills |
| Investment banking | Present | Present | Broadly aligned |
| Equity research | Present | Present | Broadly aligned |
| Private equity | Present | Present | Local version lacks `ai-readiness` |
| Wealth management | Present | Present | Broadly aligned |
| Fund administration | Missing | Present | Entire vertical missing locally |
| Operations / KYC | Missing | Present | Entire vertical missing locally |
| Partner-built LSEG | Present | Present | Aligned |
| Partner-built S&P Global | Present | Present | Aligned |

## Skill-Level Gaps by Existing Vertical

### Financial Analysis

The local `financial-analysis` plugin is the largest same-name surface that still materially differs.

| Category | Local only | Upstream only |
| --- | --- | --- |
| Commands | `3-statements`, `check-deck` | `3-statement-model` |
| Skills | `3-statements`, `check-deck`, `check-model` | `3-statement-model`, `audit-xls`, `clean-data-xls`, `deck-refresh`, `ib-check-deck`, `pptx-author`, `xlsx-author` |

Interpretation:

- Anthropic moved toward richer spreadsheet and presentation production or audit skills.
- Some local skills appear to have been renamed or split into narrower upstream variants.
- The upstream version relies more heavily on non-command utility skills that agents can call behind the scenes.

### Private Equity

| Difference | Status |
| --- | --- |
| `ai-readiness` command | Missing locally |
| `ai-readiness` skill | Missing locally |

Everything else in private equity is structurally aligned.

### Investment Banking, Equity Research, Wealth Management

These three verticals are largely aligned at the command and skill naming level. The bigger gap is not prompt coverage. The gap is that upstream Anthropic now packages those skills into named end-to-end agents and managed-agent cookbooks.

## Named Agent Layer Missing Locally

Upstream Anthropic adds ten self-contained agents that bundle skills from the verticals into workflow-specific operating packages.

| Upstream agent | Primary outcome | Skills bundled upstream | Closest local building blocks |
| --- | --- | --- | --- |
| `pitch-agent` | Build branded pitch materials end to end | `comps-analysis`, `dcf-model`, `lbo-model`, `pitch-deck`, `deck-refresh`, `pptx-author`, `xlsx-author` and others | `financial-analysis` + `investment-banking` |
| `meeting-prep-agent` | Produce pre-meeting client briefing packs | `client-review`, `client-report`, `investment-proposal`, `pptx-author` | `wealth-management` |
| `market-researcher` | Sector primer, landscape, comps, shortlist | `sector-overview`, `competitive-analysis`, `comps-analysis`, `idea-generation`, `pptx-author` | `financial-analysis` + `equity-research` |
| `earnings-reviewer` | Earnings transcript to model update to note | `earnings-analysis`, `earnings-preview`, `model-update`, `morning-note`, `audit-xls`, `xlsx-author` | `equity-research` + `financial-analysis` |
| `model-builder` | Build Excel-based valuation models | `3-statement-model`, `dcf-model`, `lbo-model`, `audit-xls`, `xlsx-author` | `financial-analysis` |
| `valuation-reviewer` | Review GP valuation packages | `ic-memo`, `portfolio-monitoring`, `returns-analysis`, `xlsx-author` | `private-equity` |
| `gl-reconciler` | Reconcile GL and trace breaks | `gl-recon`, `break-trace`, `audit-xls`, `xlsx-author` | Missing local vertical support |
| `month-end-closer` | Close support and commentary | `accrual-schedule`, `roll-forward`, `variance-commentary`, `audit-xls`, `xlsx-author` | Missing local vertical support |
| `statement-auditor` | Audit LP statements before distribution | `nav-tieout`, `audit-xls`, `xlsx-author` | Missing local vertical support |
| `kyc-screener` | Parse onboarding docs and rules | `kyc-doc-parse`, `kyc-rules`, `xlsx-author` | Missing local vertical support |

## Managed-Agent Packaging Gap

The upstream repo ships ten `managed-agent-cookbooks/<slug>/` packages. Each cookbook includes:

- `agent.yaml`
- `steering-examples.json`
- Per-agent deployment README
- A subagent structure for depth-1 delegation

This is a meaningful product surface, not just documentation. It lets the same workflow run as a deployed managed agent instead of only as a local plugin.

The local repo currently has no equivalent.

## Conclusions

- Local prompt coverage is strongest where the old marketplace was already mature: investment banking, equity research, private equity, and wealth management.
- The local repo is most outdated where Anthropic shifted from vertical bundles to end-to-end workflow agents.
- Connector parity remains strong, which means the local repo can probably be modernized without rethinking the shared data-provider baseline.
- The most strategic missing pieces are `fund-admin`, `operations`, and the agent-plus-cookbook packaging pattern.

## Source Basis

- [Anthropic financial-services repo](https://github.com/anthropics/financial-services)
- [Anthropic announcement: Agents for financial services](https://www.anthropic.com/news/finance-agents)

# Connector and Partner Update

Date: May 12, 2026

## Shared Connector Baseline

The local repo and the inspected upstream Anthropic repo still expose the same 11 shared MCP connectors in the `financial-analysis` core plugin.

| Provider | Present in local `.mcp.json` | Present in upstream `.mcp.json` |
| --- | --- | --- |
| Daloopa | Yes | Yes |
| Morningstar | Yes | Yes |
| S&P Global | Yes | Yes |
| FactSet | Yes | Yes |
| Moody's | Yes | Yes |
| MT Newswires | Yes | Yes |
| Aiera | Yes | Yes |
| LSEG | Yes | Yes |
| PitchBook | Yes | Yes |
| Chronograph | Yes | Yes |
| Egnyte | Yes | Yes |

Result: the open repo manifests still share a stable 11-connector baseline as of May 12, 2026.

## What the May 5, 2026 Article Adds

Anthropic's announcement expands the ecosystem story beyond those 11 manifest entries.

### Newly announced connectors

| Provider | Announced role |
| --- | --- |
| Dun & Bradstreet | Verified business identity and enterprise record-linking for AI workflows |
| Fiscal AI | Real-time public-equity fundamentals and benchmarking |
| Financial Modeling Prep | Quotes, fundamentals, statements, filings, and transcripts across multiple asset classes |
| Guidepoint | Compliance-reviewed expert interview transcripts |
| IBISWorld | Industry revenue, ratios, cost structures, risk scores, and forecasts |
| SS&C Intralinks | DealCenter AI data rooms, diligence Q&A, and deal-activity tracking |
| Third Bridge | Primary-source expert interviews across companies, sectors, and value chains |
| Verisk | Insurance underwriting, claims, and risk-analysis data |

### Newly announced MCP app

| Provider | Announced role |
| --- | --- |
| Moody's MCP app | Interactive use of proprietary credit ratings plus data on 600M+ public and private companies |

## Important Current-State Observation

As of May 12, 2026:

- The article names these additional partners.
- The upstream open-source repo still exposes the original 11 shared connectors in `financial-analysis/.mcp.json`.
- I did not find the newly announced provider names in the inspected upstream marketplace manifests or connector JSON files.

That means the public article is ahead of the open repo manifests on partner-surface disclosure.

## Practical Implications for This Repo

The connector roadmap now splits into two layers:

### Layer 1: Baseline shared connector stack

This repo is already aligned on the open manifest baseline. No immediate connector replacement is required to match the upstream repo's checked-in `.mcp.json`.

### Layer 2: Emerging ecosystem additions

These newly announced partners map cleanly to workflow gaps in the local repo:

| Partner | Most relevant workflow area | Why it matters |
| --- | --- | --- |
| Dun & Bradstreet | Operations / KYC | Strong fit for entity verification and onboarding |
| Guidepoint | Equity research / private equity | Adds expert-call and transcript depth |
| Third Bridge | Equity research / private equity | Similar value for primary-source diligence |
| IBISWorld | Market researcher / sector work | Strong fit for industry-primer workflows |
| SS&C Intralinks | Investment banking / private equity | Strong fit for data-room and diligence workflows |
| Verisk | Insurance and risk operations | Opens a new workflow domain not covered in the local repo |
| Fiscal AI | Public-equity analysis | Lower priority if FactSet, S&P, and Daloopa already cover the use case |
| Financial Modeling Prep | Public-markets breadth | Useful for broader or lower-cost coverage cases |
| Moody's MCP app | Credit and compliance workflows | Especially relevant if this repo grows finance-ops and KYC surfaces |

## Recommendation

For this repo, the right connector move is staged rather than immediate:

1. Keep the 11 current shared connectors as the baseline because they still match the inspected upstream manifests.
2. Document the article-announced connector layer separately so readers do not assume the repo already exposes those partners.
3. Add new partner surfaces only when the related workflow packages also exist locally, especially `fund-admin`, `operations`, and any future credit or insurance workflows.

## Source Basis

- [Anthropic financial-services repo](https://github.com/anthropics/financial-services)
- [Anthropic announcement: Agents for financial services](https://www.anthropic.com/news/finance-agents)

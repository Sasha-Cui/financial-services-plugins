# MCP Providers Used by the Claude Financial Services Reports

Date: May 12, 2026

This document updates the earlier provider report for the May 2026 Anthropic `financial-services` release. It separates three different concepts that are easy to blur together:

1. The shared MCP connectors explicitly wired into the open-source manifests
2. The partner-built workflow packages shipped in the public repo
3. The broader ecosystem partners announced in Anthropic's May 5, 2026 finance-agents article

## The Stable Shared Connector Baseline

Both the local `financial-services-plugins` repo and the inspected upstream Anthropic `financial-services` repo expose the same 11 shared MCP connectors in the `financial-analysis` core plugin.

| Provider | Manifest key | Primary role |
| --- | --- | --- |
| Daloopa | `daloopa` | Document-linked extraction of financial statement line items |
| Morningstar | `morningstar` | Investment data, fund intelligence, and research context |
| S&P Global | `sp-global` | Broad public-company, market, estimates, and transaction intelligence |
| FactSet | `factset` | Structured fundamentals, market data, and screening |
| Moody's | `moodys` | Credit ratings, outlooks, and risk commentary |
| MT Newswires | `mtnewswire` | Real-time news and catalyst flow |
| Aiera | `aiera` | Earnings events, transcripts, and management commentary |
| LSEG | `lseg` | Multi-asset pricing, analytics, curves, and fixed-income tooling |
| PitchBook | `pitchbook` | Private-market entities, deals, funds, and investors |
| Chronograph | `chronograph` | Private-capital portfolio monitoring and reporting data |
| Egnyte | `egnyte` | Internal documents, permissions, and enterprise knowledge access |

## What the 11-Connector Stack Actually Covers

The connector set works best if viewed as a layered workflow stack rather than a flat vendor list.

### Facts layer

These providers answer the structured numerical questions:

- FactSet
- S&P Global
- LSEG
- Morningstar

Typical use cases:

- Trading comps
- Valuation inputs
- Consensus estimates
- Screening and peer analysis
- Historical pricing
- Macro and market context

### Transcript and event layer

These providers answer what management, analysts, or the market actually said:

- Aiera
- MT Newswires

Typical use cases:

- Earnings-note drafting
- Catalyst tracking
- Morning notes
- Post-event synthesis

### Source-linked model update layer

- Daloopa

Typical use cases:

- Turning filings into spreadsheet-ready inputs
- Auditing whether a modeled number still ties to source support
- Refreshing historical statement tabs

### Credit and risk layer

- Moody's

Typical use cases:

- Ratings-aware financing analysis
- Capital-structure risk framing
- Credit commentary in memo or diligence workflows

### Private-markets layer

- PitchBook
- Chronograph

Typical use cases:

- Sponsor mapping
- Private comps
- Deal sourcing
- Portfolio monitoring
- LP and GP reporting support

### Internal knowledge layer

- Egnyte

Typical use cases:

- Pulling prior committee memos
- Reusing internal templates
- Accessing diligence archives
- Referencing firm-specific process documents

## Provider-by-Provider Notes

### Daloopa

Daloopa is best treated as a provenance-heavy extraction layer, not just a generic fundamentals feed. Its value is that line items are tied back to actual filings and source documents. That makes it especially strong for 3-statement refreshes, model QA, and any workflow where auditability matters.

### Morningstar

Morningstar contributes a mixed research-plus-data modality. Compared with terminal-style public-market datasets, it is better for investor framing, fund and ETF context, ratings-style interpretation, and portfolio-aware discussions.

### S&P Global

In the shared manifest, S&P Global is exposed through a Kensho-hosted integration endpoint. The practical effect is still a broad institutional facts layer: financials, prices, market cap, consensus, transactions, and related linked records. It is one of the main backbones for public-company coverage work.

### FactSet

FactSet is another core structured data layer. It is the normalized numbers engine for public-market tasks where consistency matters more than source-document extraction: screening, peer sets, estimate context, historical pricing, and market snapshots.

### Moody's

Moody's is the clearest credit-specialist layer in the shared stack. It becomes more important as the repo moves beyond equity research and investment banking into finance-ops, reconciliation, risk review, or compliance-adjacent workflows.

### MT Newswires

MT Newswires is the immediate catalyst feed. It is less about archival depth and more about answering what just happened and why a name moved.

### Aiera

Aiera is the words layer for earnings and investor communications. Its most useful feature is not just transcript availability, but machine-usable event metadata, speaker attribution, and citation-ready call detail.

### LSEG

LSEG is the broadest multi-asset and analytics-heavy provider in the public stack. It extends beyond simple quotes into curves, fixed-income analytics, options, FX carry, macro series, and YieldBook-style bond analysis.

### PitchBook

PitchBook covers the private-market landscape: companies, rounds, buyers, funds, investors, and transaction history. It matters when the universe is not confined to public issuers.

### Chronograph

Chronograph is less about market discovery and more about private-capital operating data: portfolio monitoring, valuation workflows, and recurring reporting support. It becomes more relevant once fund-admin and valuation-review flows are introduced.

### Egnyte

Egnyte is the internal memory layer. It makes the difference between a generic analyst workflow and a firm-specific one because it can surface prior internal outputs, approved templates, and controlled diligence materials.

## Partner-Built Packages in the Public Repo

The public Anthropic repo currently ships two partner-built packages on top of the shared connector set:

| Partner package | Focus |
| --- | --- |
| LSEG | Bond RV, swap curves, FX carry, option vol, fixed-income portfolio review, macro-rates monitoring |
| S&P Global | Tear sheets, earnings previews, and funding digests |

These packages are not separate connector categories from the shared stack. They are deeper workflow wrappers around providers that are already part of the main connector baseline.

## What Anthropic Announced on May 5, 2026 Beyond the Open Manifests

Anthropic's finance-agents announcement introduced a broader ecosystem story than the 11 wired connectors shown in the checked-in `.mcp.json` files.

### Newly announced ecosystem partners

| Partner | Stated value in the announcement |
| --- | --- |
| Dun & Bradstreet | Verified business identity and enterprise record-linking for AI workflows |
| Fiscal AI | Real-time public-equity fundamentals and benchmarking |
| Financial Modeling Prep | Quotes, fundamentals, statements, filings, and transcripts |
| Guidepoint | Compliance-reviewed expert interview transcripts |
| IBISWorld | Industry revenue, cost structure, risk, and forecast data |
| SS&C Intralinks | DealCenter AI data rooms, diligence Q&A, and deal tracking |
| Third Bridge | Expert interviews across companies, sectors, and value chains |
| Verisk | Insurance underwriting, claims, and risk-analysis data |

### Newly announced app surface

| Surface | Stated role |
| --- | --- |
| Moody's MCP app | Interactive use of proprietary credit data plus coverage of 600M+ public and private companies |

## Important Distinction

As of May 12, 2026:

- These additional partners are part of Anthropic's public narrative.
- They are not yet reflected in the inspected upstream open-source connector manifests.
- The open repo still centers on the stable 11-connector baseline plus two partner-built packages.

That distinction matters for planning. A repo can be "aligned with the open manifests" while still not matching the full ecosystem breadth Anthropic is now marketing.

## Implications for This Repo

### What is already aligned

- The shared 11-connector baseline
- The LSEG partner-built package
- The S&P Global partner-built package

### What should be treated as next-wave connector opportunities

| Partner | Best matching future workflow area |
| --- | --- |
| Dun & Bradstreet | Operations and KYC |
| Guidepoint | Equity research and private equity diligence |
| Third Bridge | Equity research and private equity diligence |
| IBISWorld | Market-research and sector-primer workflows |
| SS&C Intralinks | Investment banking and private-equity data-room workflows |
| Verisk | Insurance and risk operations |
| Financial Modeling Prep | Broader public-markets coverage or lower-cost data coverage cases |
| Fiscal AI | Supplemental public-equity coverage workflows |
| Moody's MCP app | Credit-heavy finance, risk, and onboarding workflows |

## Bottom Line

The connector story is more stable than the packaging story.

- Packaging changed dramatically in May 2026: agents, cookbooks, and Microsoft 365 tooling
- The open shared connector baseline did not

That means the fastest way to modernize this repo is still to adopt the new workflow surfaces first, while treating the article-announced partner set as a second-wave roadmap rather than assuming those integrations are already represented in the open manifests.

## Source Basis

- Anthropic `financial-services` repo inspected on May 12, 2026
- Anthropic "Agents for financial services" announcement published on May 5, 2026

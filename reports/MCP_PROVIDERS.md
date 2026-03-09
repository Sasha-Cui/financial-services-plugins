# MCP Providers Used by the Claude Cowork Financial Services Plugins

- **Facts layer (numbers, comps, consensus):** FactSet / Capital IQ / LSEG
- **Words layer (what was said):** Aiera
- **Now layer (what just happened):** MT Newswires
- **Model-update layer (turn filings into spreadsheet inputs):** Daloopa
- **Risk lens (credit):** Moody's
- **Private markets (if relevant):** PitchBook / Chronograph
- **Internal knowledge base:** Egnyte

## At a Glance

| Provider     | MCP key       | Endpoint host               | Primary modality                           | Typical payload shape                                                       |
| ------------ | ------------- | --------------------------- | ------------------------------------------ | --------------------------------------------------------------------------- |
| Daloopa      | `daloopa`     | `mcp.daloopa.com`           | Structured extracted financial data        | Normalized line items with document provenance                              |
| Morningstar  | `morningstar` | `mcp.morningstar.com`       | Research plus investment data              | Security/fund attributes, analytics, ratings, research text                 |
| S&P Global   | `sp-global`   | `kfinance.kensho.com`       | Structured company and market intelligence | Financials, prices, consensus, transactions, linked source records          |
| FactSet      | `factset`     | `mcp.factset.com`           | Structured market and fundamentals data    | Standardized market data, fundamentals, estimates, screening results        |
| Moody's      | `moodys`      | `api.moodys.com`            | Credit ratings and credit research         | Ratings, outlook/watch status, research and risk context                    |
| MT Newswires | `mtnewswire`  | `vast-mcp.blueskyapi.com`   | Real-time news text                        | Timestamped headlines, briefs, and market-moving updates                    |
| Aiera        | `aiera`       | `mcp-pub.aiera.com`         | Event and transcript data                  | Earnings events, speaker-tagged transcript text, playback-linked excerpts   |
| LSEG         | `lseg`        | `api.analytics.lseg.com`    | Multi-asset market data and analytics      | Prices, curves, vol surfaces, fixed-income analytics, macro series          |
| PitchBook    | `pitchbook`   | `premium.mcp.pitchbook.com` | Private markets intelligence               | Company, deal, fund, investor, and valuation records                        |
| Chronograph  | `chronograph` | `ai.chronograph.pe`         | Private-capital portfolio data             | Portfolio metrics, valuations, reporting data, warehousing-oriented records |
| Egnyte       | `egnyte`      | `mcp-server.egnyte.com`     | Enterprise documents and governance        | Files, folders, metadata, permissions, governance context                   |

## What "data modality" means here

For this document, "data modality" means the shape of information Claude is likely to receive from the provider, not just the vendor category. In practice, these modalities fall into a few buckets:

- **Structured numeric and tabular data**: financial line items, prices, ratios, consensus estimates, curves, time series, transactions, portfolio metrics.
- **Research and news text**: articles, briefs, ratings commentary, analyst-style writeups, summaries.
- **Transcript and event text**: speaker-attributed earnings-call transcripts, event metadata, timestamps, playback-linked excerpts.
- **Document-linked data**: numbers that are traceable back to filings, decks, or source documents.
- **Enterprise content objects**: files, folders, permissions, governance metadata, and stored internal documents.

Most of the providers in this repo are mixed-modality systems rather than pure single-format feeds, but each one has a clear primary shape.

## Provider-by-Provider Notes

### Daloopa

Daloopa is best understood as a **document-linked financial data extraction layer** rather than a broad terminal-style market-data platform. Its strongest modality is structured numeric data pulled from filings, earnings materials, and other financial documents, with traceability back to the source. That means the payload is not just "revenue = X"; it is usually "revenue = X, from this filing or this table, with provenance you can audit."

That makes Daloopa especially useful when Claude is updating a model or checking whether a number in a spreadsheet still ties back to the primary source. The modality is mostly tabular and numeric, but the critical secondary modality is **source linkage** to the underlying document.

### Morningstar

Morningstar is a **research-plus-data** provider. Compared with FactSet, S&P Global, or LSEG, its center of gravity is less "market plumbing" and more investment intelligence: fund and ETF data, security analysis, ratings, portfolio analytics, screening, and research content. The modality is therefore mixed: partly structured attributes and analytics, partly authored research and evaluation.

Inside a Claude workflow, Morningstar is most useful when the user needs investor-facing interpretation, fund context, or portfolio analytics rather than just a raw reported number. If the task is "what do we know about this fund, this ETF, or this covered name, and how is it positioned?", Morningstar is usually a better fit than a pure pricing feed.

### S&P Global

S&P Global in this repo shows up as the MCP key `sp-global`, but the configured endpoint is served from `kfinance.kensho.com`. The practical implication is important: **Kensho is the AI delivery layer, while the underlying provider is S&P Global data**, especially Capital IQ-style company, market, estimates, and transaction data.

The repo's partner-built S&P materials make the expected modality very concrete. The skills reference structured function calls such as `get_financial_line_item_from_identifiers`, `get_prices_from_identifiers`, `get_capitalization_from_identifiers`, and `get_consensus_estimates_from_identifiers`, which strongly suggests a primary modality of **structured numeric financial and market intelligence**. In practice, that means company financials, prices, market cap, consensus estimates, transactions, and related metadata that can be cited down to the tool-call level.

This is the connector you use when Claude needs a broad, institution-grade facts layer for tearsheets, earnings previews, comps, or market-mapping work.

### FactSet

FactSet is another **broad structured financial data platform**. Its likely modality in an MCP context is standardized company fundamentals, market data, estimates, ownership, screening results, and related entity/security metadata. In other words, it is optimized for machine-usable financial facts rather than transcript-first or document-storage-first workflows.

For Claude, FactSet is most valuable when the job is to establish a consistent numbers layer across public companies: price history, key metrics, consensus framing, peer comparisons, and screening outputs. Relative to Daloopa, the modality is less about source-document extraction and more about normalized financial datasets and workflow-ready market intelligence.

### Moody's

Moody's brings a **credit modality** that the broader market-data providers do not emphasize in the same way. Its primary payloads are ratings, outlooks, watchlists, credit opinions, and credit research, plus broader risk and analytics content depending on entitlements.

That means the useful shape of the data is partly discrete and stateful, such as a current rating or outlook, and partly narrative, such as a rationale for a downgrade risk or sector credit pressure. In earnings and financing workflows, Moody's is the risk lens you want when capital structure, refinancing, covenant headroom, or rating sensitivity matters as much as revenue or EBITDA.

### MT Newswires

MT Newswires is primarily a **real-time news text feed**. Its modality is not a fundamentals table or a document store; it is a stream of timestamped headlines and short market-oriented stories designed to be consumed quickly. The important payload characteristics are speed, timestamps, ticker/company tagging, and concise market-moving summaries.

That makes it the connector for "what happened just now?" questions around earnings releases, guidance changes, analyst reactions, peer sympathy moves, management commentary, or other catalysts. If Claude needs to explain the immediate catalyst layer around a stock move, MT Newswires is a natural fit.

### Aiera

Aiera is the clearest **transcript and investor-event modality** in the connector set. Its value is not simply that it covers earnings calls; it is that it turns those events into machine-usable artifacts such as event metadata, transcript text, timestamps, speaker attributions, search, and playback-linked excerpts.

That gives Claude access to the "words layer" of the workflow: what management actually said, how guidance language changed, which topics dominated the Q&A, and how to cite a statement to a specific speaker or moment in the call. The modality is therefore a hybrid of event metadata and unstructured transcript text, sometimes paired with audio or replay controls on the vendor side.

### LSEG

LSEG is the broadest **multi-asset pricing and analytics** modality in the repo. The local partner-built [LSEG connector reference](../partner-built/lseg/CONNECTORS.md) shows a tool surface that includes bond pricing, FX spot and forwards, interest-rate and credit curves, swap pricing, options, volatility surfaces, historical equity prices, macroeconomic series, and YieldBook fixed-income analytics.

That is more than "market data" in the narrow sense. The payloads here are often analytical objects: curves, surfaces, scenario outputs, Greeks, durations, cashflows, and risk measures. So the modality is structured numeric data, but in a quantitatively derived form suited for rates, FX, options, and fixed income workflows rather than just simple quote retrieval.

### PitchBook

PitchBook is a **private markets intelligence** provider. Its core modality is structured records about private companies, deals, investors, funds, rounds, valuations, and market activity in venture capital, private equity, and M&A-adjacent workflows. It also carries research and workflow tooling, but the most important MCP-ready shape is the linked record set around entities and transactions.

In practice, PitchBook is what Claude should reach for when the universe is not limited to listed companies: sponsor mapping, private comps, prior financing rounds, investor ownership, deal history, or fund activity. The modality is structured private-market metadata with some research context around it.

### Chronograph

Chronograph is another private-markets source, but with a different center of gravity from PitchBook. Its modality is **portfolio monitoring, reporting, and valuation data for private capital workflows**, especially GP and LP operating processes. That means portfolio company metrics, periodic reporting data, valuation workflows, and data-management structures that are closer to internal operating records than to an external newswire.

If PitchBook tells Claude about the market and transaction landscape, Chronograph is more about the ongoing measurement and reporting layer for owned assets and funds. It is especially relevant when the user is working on portfolio reviews, LP reporting, valuation support, or performance monitoring.

### Egnyte

Egnyte is the only connector in the main shared stack whose primary modality is **enterprise content rather than financial market data**. The useful payloads here are files, folders, previews, metadata, permissions, and governance controls across internal documents.

That makes Egnyte the bridge between Claude and the firm's internal knowledge base: prior models, committee memos, templates, diligence files, client materials, and archived outputs. In modality terms, this is document retrieval and document governance, not market intelligence. It matters because many financial workflows combine external data with internal precedent and controlled document access.

## Important Repo Nuances

### The core plugin owns the shared connectors

The main architectural fact in this repo is that the shared connector list is centralized in [`financial-analysis/.mcp.json`](./.mcp.json). The workflow-specific plugins are mostly instructions and commands layered on top of that.

### Kensho is a delivery layer here, not a separate shared provider

It is reasonable to mention Kensho when discussing the S&P integration, because the S&P endpoint in this repo is hosted on `kfinance.kensho.com` and the partner-built S&P plugin is maintained by Kensho. But the underlying provider in the shared connector list is still best described as **S&P Global / Capital IQ-style data delivered through Kensho's integration surface**, not as a separate twelfth data provider.

### LSEG and S&P also appear as partner-built plugins

The repo also includes vendor-specific packages for [LSEG](../partner-built/lseg/README.md) and [S&P Global](../partner-built/spglobal/README.md). Those do not add new provider categories to the shared core list; they package deeper vendor-specific workflows and prompt logic around providers that are already present in the main connector stack.

## Sources

### Repository sources

- [Root README](../README.md)
- [Core MCP config](./.mcp.json)
- [Investment banking MCP config](../investment-banking/.mcp.json)
- [Private equity MCP config](../private-equity/.mcp.json)
- [LSEG connector reference](../partner-built/lseg/CONNECTORS.md)
- [LSEG partner-built plugin README](../partner-built/lseg/README.md)
- [S&P Global partner-built plugin README](../partner-built/spglobal/README.md)
- [S&P earnings preview skill](../partner-built/spglobal/skills/earnings-preview-beta/SKILL.md)

### Vendor sources

- [Daloopa](https://daloopa.com/benefits/sec-filings-in-spreadsheets)
- [Morningstar Direct Web Services](https://www.morningstar.com/business/products/direct-web-services)
- [S&P Capital IQ Pro](https://www.spglobal.com/market-intelligence/en/solutions/products/sp-capital-iq-pro)
- [FactSet](https://www.factset.com/)
- [Moody's ratings and research](https://www.moodys.com/)
- [MT Newswires](https://www.mtnewswires.com/)
- [Aiera platform](https://aiera.com/platform/)
- [Aiera Core Data MCP](https://aiera.readme.io/reference/getting-started-with-aiera-core-data-mcp)
- [LSEG data and analytics](https://www.lseg.com/en/data-analytics)
- [PitchBook](https://pitchbook.com/)
- [Chronograph](https://www.chronograph.pe/general-partners/)
- [Egnyte platform](https://www.egnyte.com/products/platform)

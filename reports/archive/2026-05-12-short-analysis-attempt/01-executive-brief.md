# Executive Brief

Date: May 12, 2026

## What changed on May 5, 2026

Anthropic materially expanded its public financial-services reference offering on May 5, 2026. The change is not just new marketing language. The public package now combines:

- Ten ready-to-run named agent templates
- Seven vertical or shared workflow plugins
- Ten managed-agent cookbooks for headless deployment
- A Microsoft 365 add-in provisioning tool
- A broader partner and connector story than the one exposed in the older vertical-only marketplace

The announcement also anchors the release to a specific execution model:

- Plugins for Claude Cowork and Claude Code
- Cookbooks for Claude Managed Agents
- Cross-application work in Excel, PowerPoint, Word, and Outlook
- More governed access to external financial data and internal systems

## Why it matters for this repo

This local repo still represents the earlier shape of the marketplace: five workflow plugins plus two partner-built plugins, with no named agents, no managed-agent cookbooks, and no Microsoft 365 deployment tooling.

That means the repo is still useful as a vertical skill bundle, but it no longer matches Anthropic's latest public reference architecture.

## Headline findings

- The shared connector baseline is still aligned. Both repos expose the same 11 shared MCP servers in the `financial-analysis` core plugin.
- The architectural surface is no longer aligned. Anthropic now ships a dual-surface model: reusable vertical plugins plus self-contained named agents.
- The largest gaps are not in investment-banking or equity-research prompts. They are in packaging, orchestration, and finance-ops coverage.
- The biggest missing capability areas are `fund-admin`, `operations`, managed-agent cookbooks, and self-contained agent wrappers.
- Anthropic's article announces additional ecosystem partners and a Moody's MCP app, but those additions are not yet represented in the inspected open repo manifests as of May 12, 2026.

## Quantitative snapshot

| Metric | Local repo | Anthropic upstream |
| --- | ---: | ---: |
| Vertical plugins | 5 | 7 |
| Named agent plugins | 0 | 10 |
| Partner-built plugins | 2 | 2 |
| Managed-agent cookbooks | 0 | 10 |
| Total commands | 47 | 47 |
| Total skills | 53 | 117 |
| Shared MCP connectors | 11 | 11 |
| Microsoft 365 install tooling packages | 0 | 1 |

The command count staying flat while the skill count more than doubles is important. Anthropic added depth, packaging, and automation surfaces rather than simply adding more slash commands.

## Immediate implication

If the goal is to keep this repo current relative to Anthropic's May 2026 financial-services release, the next update should prioritize structure and deployment surfaces before prompt polishing:

1. Add the missing verticals and missing shared skills.
2. Introduce self-contained named agent plugins.
3. Add managed-agent cookbooks that point to the same source prompts.
4. Decide whether this repo also wants Microsoft 365 deployment tooling or only the workflow content.

## Source Basis

- [Anthropic financial-services repo](https://github.com/anthropics/financial-services)
- [Anthropic announcement: Agents for financial services](https://www.anthropic.com/news/finance-agents)

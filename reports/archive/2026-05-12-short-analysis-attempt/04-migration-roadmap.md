# Migration Roadmap

Date: May 12, 2026

## Goal

Bring `/Users/cui/Documents/GitHub/financial-services-plugins` materially closer to Anthropic's May 2026 financial-services reference architecture without losing the current repo's simpler plugin-first ergonomics.

## Recommended Sequence

## Phase 1: Structural alignment

Target outcome: make the repo shape recognizable relative to Anthropic's public reference repo.

Recommended changes:

1. Move current vertical plugins under `plugins/vertical-plugins/`.
2. Move current partner packages under `plugins/partner-built/`.
3. Update `.claude-plugin/marketplace.json` to point at the nested locations.
4. Rename or alias marketplace references toward `claude-for-financial-services` if branding alignment matters.

Why first:

- This is the least ambiguous divergence.
- It reduces future porting friction.
- It creates clean landing zones for agent plugins and cookbooks.

## Phase 2: Fill missing vertical coverage

Target outcome: close the biggest workflow gaps before building wrappers around them.

Recommended additions:

1. Add `plugins/vertical-plugins/fund-admin/` with at least:
   `gl-recon`, `break-trace`, `accrual-schedule`, `roll-forward`, `variance-commentary`, `nav-tieout`
2. Add `plugins/vertical-plugins/operations/` with at least:
   `kyc-doc-parse`, `kyc-rules`
3. Add `ai-readiness` to `private-equity`.
4. Backfill the richer financial-analysis utilities:
   `audit-xls`, `clean-data-xls`, `deck-refresh`, `ib-check-deck`, `pptx-author`, `xlsx-author`

Why second:

- The missing agents depend on these skills.
- The article's operations and finance-ops positioning cannot be represented honestly without them.

## Phase 3: Add named agent plugins

Target outcome: package existing vertical logic into self-contained workflow agents.

Recommended first-wave agents:

1. `pitch-agent`
2. `market-researcher`
3. `earnings-reviewer`
4. `meeting-prep-agent`
5. `model-builder`

Why these first:

- They reuse the strongest local vertical coverage.
- They map directly to the public announcement.
- They create visible parity quickly without waiting for the entire finance-ops stack.

Recommended second-wave agents:

1. `valuation-reviewer`
2. `gl-reconciler`
3. `month-end-closer`
4. `statement-auditor`
5. `kyc-screener`

Why these later:

- They depend on the missing `fund-admin` and `operations` verticals.

## Phase 4: Add managed-agent cookbooks

Target outcome: support both plugin installation and headless managed-agent deployment from one prompt source.

Recommended additions per agent:

- `managed-agent-cookbooks/<slug>/agent.yaml`
- `managed-agent-cookbooks/<slug>/README.md`
- `managed-agent-cookbooks/<slug>/steering-examples.json`
- `managed-agent-cookbooks/<slug>/subagents/`

Also add:

- A sync script similar to Anthropic's `scripts/sync-agent-skills.py`
- A validation script that checks bundled-agent skills against vertical sources

Why this matters:

- This is the core of Anthropic's "same source, same skills, two deployment surfaces" model.

## Phase 5: Decide on Microsoft 365 scope

Target outcome: explicitly choose whether this repo should remain workflow-only or also include enterprise deployment tooling.

Options:

- Keep this repo workflow-only and document Microsoft 365 as out of scope.
- Add a `claude-for-msft-365-install/` package if direct parity with Anthropic's public release is the goal.

Recommendation:

- Only add Microsoft 365 install tooling if this repo is intended to be a true reference distribution rather than just a plugin marketplace.

## Phase 6: Document the ecosystem delta

Target outcome: keep users from confusing article-announced partner scope with checked-in manifest scope.

Recommended documentation updates:

1. Separate "currently wired connectors" from "announced ecosystem partners".
2. Call out that the open repo baseline still reflects 11 shared connectors as of May 12, 2026.
3. Tie future connector additions to the workflows they unlock, especially KYC, diligence data rooms, expert networks, and insurance workflows.

## Recommended Order of Execution

| Priority | Workstream | Reason |
| --- | --- | --- |
| 1 | Structural alignment | Low ambiguity, unblocks everything else |
| 2 | Fund-admin and operations verticals | Biggest functional gaps |
| 3 | Financial-analysis utility backfill | Needed for model and deck agents |
| 4 | First-wave named agents | Fastest visible parity gains |
| 5 | Managed-agent cookbooks | Completes the dual-surface deployment model |
| 6 | Microsoft 365 tooling decision | Important, but optional |
| 7 | Additional connector exposure | Should follow workflow ownership, not lead it |

## Bottom Line

The shortest path to a credible refresh is not to rewrite the existing prompts. It is to preserve the current vertical content, add the missing workflow domains, and then package the result the way Anthropic now packages its public reference offer: verticals plus agents plus managed-agent cookbooks.

## Source Basis

- [Anthropic financial-services repo](https://github.com/anthropics/financial-services)
- [Anthropic announcement: Agents for financial services](https://www.anthropic.com/news/finance-agents)

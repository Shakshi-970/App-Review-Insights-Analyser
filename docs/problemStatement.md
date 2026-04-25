Problem Statement
Weekly Product Review Pulse — Problem Statement
We are building an **AI Agent** that manages an automated weekly “pulse” for fintech products. The agent turns public App Store and Google Play reviews into structured insights and delivers them by **using MCP (Model Context Protocol) tools** to interact with Google Docs and Gmail. This ensures that the agent performs actions via dedicated MCP servers rather than direct API calls, maintaining security and modularity.
Supported products (initial): INDMoney, Groww, PowerUp Money, Wealth Monitor, Kuvera.

Objective
Give product, support, and leadership teams a repeatable, weekly snapshot of what customers are saying in store reviews: themes, representative quotes, and actionable ideas—without manual copy-paste or one-off spreadsheets.

What the agent does
Ingest public reviews from the last 8–12 weeks (configurable window) from both Apple App Store (e.g. iTunes customer-reviews RSS) and Google Play (scraper-based), per product.
Cluster and rank feedback using embeddings and density-based clustering (e.g. UMAP + HDBSCAN), then use an LLM to name themes, pull verbatim quotes, and propose action ideas—with validation so quotes must appear in real review text.
Render a concise one-page narrative: top themes, quotes, action ideas, and a short “who this helps” section.
Deliver outputs only through Google Workspace MCP servers:
Google Docs MCP — append each week’s report as a new dated section to a single running document per product (e.g. Weekly Review Pulse — Groww). The Doc is the system of record and preserves history.
Gmail MCP — send a short stakeholder email that includes a deep link to the new section in that Doc (heading link), not a duplicate full report in email alone.
Internal code stays modular along these lines (see [architecture.md](file:///c:/Users/shakshi.d.singh/OneDrive%20-%20Accenture/M3/docs/architecture.md) for details):

| Phase | Concern | Where it lives (`src/`) |
| :--- | :--- | :--- |
| **Phase 0** | **Foundations** | `phase0_foundations/` (Config, Models, Run Log) |
| **Phase 1** | **Data retrieval** | `phase1_ingestion/` (App Store + Play Store + PII Scrub) |
| **Phase 2** | **Thematic grouping** | `phase2_clustering/` (Embeddings + UMAP + HDBSCAN) |
| **Phase 3** | **Reasoning** | `phase3_summarization/` (LLM Themes, Quotes, Actions) |
| **Phase 4** | **Output generation** | `phase4_renderer/` (Markdown & HTML formatting) |
| **Phase 5** | **Docs Delivery** | `phase5_docs_mcp/` (Google Docs MCP Client) |
| **Phase 6** | **Email Delivery** | `phase6_gmail_mcp/` (Gmail MCP Client) |
| **Phase 7** | **Orchestration** | `phase7_orchestration/` (Agent Loop & Tool Registry) |

The agent is an MCP host/client; it does not embed Google credentials or call the Docs/Gmail REST APIs directly for delivery.

Key requirements
MCP-based delivery: Append to the shared Google Doc and send Gmail only via the respective MCP servers’ tools (e.g. document batch update, draft/create/send flows as defined in architecture).
Weekly cadence: Designed to run once per product per week (e.g. scheduled job Monday morning IST), with a CLI for backfill of any ISO week.
Idempotent runs: Re-running the same product + ISO week must not create duplicate Doc sections or duplicate sends. This is enforced via stable section anchors in the Doc, email history checks, and Orchestrator-level locks in the Run Log (see [architecture.md](file:///c:/Users/shakshi.d.singh/OneDrive%20-%20Accenture/M3/docs/architecture.md)).
Auditable: Every run and tool interaction is persisted in a SQLite-based **Run Log (Phase 0)**, recording delivery identifiers (Doc heading URLs, Gmail message IDs) and token usage to answer “what was sent when, for which week?”
Safety and quality: PII scrubbing on review text before LLM and before publishing; reviews treated as data, not instructions; cost/token limits per run.

Non-goals (explicit)
A generic Google Workspace product beyond what the pulse needs (Docs append + Gmail send/draft).
Real-time streaming analytics or a BI dashboard (the running Google Doc is the living artifact).
Social sources (Twitter, Reddit, etc.) in the initial scope.
Storing Google OAuth secrets in the agent codebase—they belong in the MCP servers’ configuration, per architecture.

Who this helps
Audience
Value
Product
Prioritize roadmap from recurring themes
Support
Spot repeating complaints and quality issues
Leadership
Fast health snapshot tied to customer voice


Sample output (illustrative)
Groww — Weekly Review Pulse
Period: Last 8–12 weeks (rolling window)
Top themes
App performance & bugs — Lag, crashes during trading hours; login/session timeouts.
Customer support friction — Slow responses; unresolved tickets.
UX & feature gaps — Confusing navigation for portfolio insights; missing advanced analytics.
Real user quotes
“The app freezes exactly when the market opens, very frustrating.”
“Support takes days to reply and doesn’t solve the issue.”
“Good for beginners but lacks detailed analysis tools.”
Action ideas
Stabilize peak-time performance — Scale infra during market hours; improve crash visibility.
Improve support SLA visibility — Expected response time in-app; ticket status tracking.
Enhance power-user features — Advanced portfolio analytics; clearer investments navigation.
What this solves
Same intent as today: roadmap alignment for product, issue clustering for support, and a leadership-friendly snapshot—now automated, archived in Google Docs, and announced by email with a link back to the canonical section.

Delivery expectations (stakeholder-facing)
Each run adds one clearly labeled section to the product’s pulse Google Doc (dated / week-labeled).
The email is a brief teaser (e.g. top themes as bullets) plus a “Read full report” link to that section.
Development/staging may default to draft-only email until explicit confirmation to send, per implementation plan.

Success criteria (high level)
End-to-end run produces a grounded one-page pulse (themes, validated quotes, actions) for a configured product and window.
Doc and email outcomes are idempotent per product + week.
Security Compliance: All Workspace actions are performed through MCP servers with zero Google credentials stored in the agent's environment or code.
Architecture and implementation plan traceability: every requirement above maps to modules, MCP usage, and phased exit criteria in docs/architecture.md and docs/implementationPlan.md.

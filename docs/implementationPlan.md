# Implementation Plan — Weekly Product Review Pulse AI Agent

This plan maps each phase to concrete tasks, files to create, dependencies, and exit criteria.

---

## Phase 0 — Foundations
**Directory**: `src/phase0_foundations/`
**Goal**: Establish shared infrastructure that every later phase depends on.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 0.1 | Centralized config | `config.py` | Use `pydantic-settings` to load `.env` — GROQ_API_KEY, product list, rolling window size, MCP server params, Gmail OAuth2 credentials |
| 0.2 | Data models | `models.py` | Define `Review`, `CleanReview`, `Cluster`, `Theme`, `PulseReport`, `RenderedReport`, `RunRecord` with Pydantic |
| 0.3 | Run log | `run_log.py` | SQLite-backed CRUD with in-memory fallback (UUID-based shared-cache URI) for locked/read-only environments |
| 0.4 | Requirements | `requirements.txt` | Pin all dependencies including `fastapi`, `uvicorn[standard]`, `google-auth-oauthlib` |
| 0.5 | Environment template | `.env.example` | Document every expected env var including Gmail API OAuth2 keys |

### Exit Criteria
- All models serialize/deserialize without error.
- Run log can create, read, and update records; falls back to in-memory when file I/O is blocked.
- `config.py` loads settings from `.env` or falls back to defaults.

---

## Phase 1 — Ingestion
**Directory**: `src/phase1_ingestion/`
**Goal**: Fetch, normalize, and clean public reviews.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 1.1 | App Store scraper | `appstore_scraper.py` | Parse iTunes RSS XML; extract review_id, rating, title, text, date; handle pagination |
| 1.2 | Play Store scraper | `playstore_scraper.py` | Use `google-play-scraper`; extract same fields; handle continuation tokens |
| 1.3 | PII scrubber | `pii_scrubber.py` | Regex patterns for emails, phones, Aadhaar-like IDs; preserve `original_text` before scrubbing; strip emojis |
| 1.4 | Deduplication | In scrapers | Deduplicate by `review_id` across runs |
| 1.5 | Rolling window filter | In scrapers | Only return reviews within `ROLLING_WINDOW_WEEKS` from today |
| 1.6 | Parallel scraping | `agent.py` | App Store and Play Store scraped concurrently via `ThreadPoolExecutor(max_workers=2)` — ~2x faster |

### Exit Criteria
- Scrapers return `List[CleanReview]` for at least 2 products.
- PII scrubber catches 100% of synthetic test PII patterns.
- No duplicate `review_id` values in output.
- Both stores scraped in parallel, total scrape time under 30s.

---

## Phase 2 — Clustering
**Directory**: `src/phase2_clustering/`
**Goal**: Group clean reviews into thematic clusters.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 2.1 | Embedder | `embedder.py` | Use `sentence-transformers/all-MiniLM-L6-v2`; load with `local_files_only=True` first (avoids httpx revision-check calls on restricted networks); batch-encode review texts; return NumPy array |
| 2.2 | Clusterer | `clusterer.py` | UMAP (`n_neighbors=5`, `min_dist=0.1`, `n_components=2`) → HDBSCAN (`min_cluster_size=5`, `min_samples=1`); return `List[Cluster]` |
| 2.3 | Noise handling | `clusterer.py` | Reviews in cluster -1 (noise) placed in an "Other" bucket |
| 2.4 | Representative selection | `clusterer.py` | For each cluster, select top-k reviews closest to centroid |
| 2.5 | Progress logging | `clusterer.py` | Detailed per-step timing logs: UMAP duration, HDBSCAN duration, cluster size breakdown |

### Exit Criteria
- Given ≥50 reviews, produces ≥2 meaningful clusters.
- Each cluster contains a `centroid_indices` list of ≤10 representatives.
- UMAP completes in <90s for 2000 reviews (n_neighbors=5 is ~2x faster than default 10).

---

## Phase 3 — Summarization
**Directory**: `src/phase3_summarization/`
**Goal**: Use the LLM to name themes, pick quotes, and generate action ideas.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 3.1 | Prompt templates | `prompts.py` | System prompt + per-cluster user prompt; include tone guide, output JSON schema, and explicitly prohibit emojis |
| 3.2 | Synthesizer | `synthesizer.py` | Send cluster representatives to Groq/Llama3; parse structured JSON response into `Theme` objects |
| 3.3 | Quote validator | `quote_validator.py` | For each LLM-returned quote, verify it exists as a substring in the original review corpus; reject invalid quotes |
| 3.4 | Token budgeting | `synthesizer.py` | Track cumulative token usage; abort if budget exceeded |

### Exit Criteria
- Every quote in the output passes validation (100% grounded).
- LLM returns valid JSON parseable into `List[Theme]`.
- Token usage per run stays within configured budget.

---

## Phase 4 — Renderer
**Directory**: `src/phase4_renderer/`
**Goal**: Convert structured data into ready-to-deliver formats.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 4.1 | Doc renderer | `doc_renderer.py` | Convert `PulseReport` → Markdown with heading `## Weekly Pulse — {product} — Week {iso_week}`; limit themes/quotes to fit 1 page |
| 4.2 | Email renderer | `email_renderer.py` | Convert `PulseReport` → HTML teaser: top 3 theme bullets + "Read full report" deep link |
| 4.3 | Heading anchor | `doc_renderer.py` | Generate a stable anchor string `pulse-{product}-{iso_week}` for idempotency checks |

### Exit Criteria
- Doc Markdown renders correctly in Google Docs.
- Email HTML renders in major clients (Gmail web, Outlook).
- Heading anchor is deterministic for the same product + week.

---

## Phase 5 — Google Docs MCP (FastMCP)
**Directory**: `src/phase5_docs_mcp/`
**Goal**: Append the rendered report to the product's Google Doc via a custom FastMCP server.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 5.1 | Create FastMCP Server | `server.py` | Implement a custom MCP server using `FastMCP` with tools for `docs_get_document` and `docs_batch_update` |
| 5.2 | MCP Client setup | `docs_client.py` | Connect to the local `server.py` using `stdio_client` automatically, or remote SSE URL if `GOOGLE_DOCS_MCP_SERVER_URL` is set |
| 5.3 | Idempotency check | `docs_client.py` | Read Doc content via the tool; search for the week's heading anchor; skip if found |
| 5.4 | Append section | `docs_client.py` | Call `docs_batch_update` to insert the Markdown section at the top of the Doc |

### Exit Criteria
- `server.py` starts and exposes tools successfully.
- `docs_client.py` can communicate with the server and perform the append logic.
- Returns a valid deep-link URL.

---

## Phase 6 — Gmail MCP (FastMCP)
**Directory**: `src/phase6_gmail_mcp/`
**Goal**: Send a teaser notification email via a custom FastMCP server.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 6.1 | Create FastMCP Server | `server.py` | Implement a custom MCP server using `FastMCP` with tools for `gmail_send_message` and `gmail_create_draft` |
| 6.2 | MCP Client setup | `gmail_client.py` | Connect to the local `server.py` using `stdio_client`, or remote SSE URL if `GMAIL_MCP_SERVER_URL` is set |
| 6.3 | Send Teaser | `gmail_client.py` | Call the appropriate tool based on `SEND_MODE` (draft vs send) |
| 6.4 | Idempotency | `gmail_client.py` | Check `run_log` for existing `email_message_id` for this `(product, iso_week)` |

### Exit Criteria
- Draft email appears in Gmail drafts with correct content and deep-link.
- Re-running does not send a duplicate email.
- Returns `message_id` for audit logging.

---

## Phase 7 — Orchestration
**Directory**: `src/phase7_orchestration/`
**Goal**: Wire everything together as an AI Agent reasoning loop.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 7.1 | Agent loop | `agent.py` | Fixed-order pipeline (no LLM routing overhead): scrape → cluster → summarize → render → publish → email |
| 7.2 | Lazy loading | `agent.py` | Heavy objects (Embedder, Synthesizer, etc.) deferred via `@property` — only loaded when the phase runs |
| 7.3 | Error handling | `agent.py` | Retry on transient failures (rate-limit, connection, timeout) with exponential backoff; email failure is non-fatal |
| 7.4 | Run lifecycle | `agent.py` | Idempotency check at start; `RunRecord` logged at end with all delivery IDs |
| 7.5 | CLI entry point | `agent.py` | `python -m src.phase7_orchestration.agent --product Groww --week 2026-W17` |
| 7.6 | Backfill mode | `agent.py` | `--backfill` flag runs for all missing weeks in the rolling window |
| 7.7 | Pause email flag | `agent.py` | `--pause-email` drafts the email but does not send; portal uses this to hold for user approval |

### Exit Criteria
- End-to-end run: Agent fetches reviews → clusters → summarizes → renders → appends Doc → sends email.
- Idempotent: re-running the same product + week is a no-op.
- All steps logged in `run_log.db` with delivery IDs.

---

## Phase 8 — Portal (Demo UI)
**Directory**: `src/portal/`
**Goal**: Provide a browser-based interface to trigger and monitor the full pipeline live.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 8.1 | FastAPI backend | `app.py` | POST `/run` starts the agent subprocess; GET `/stream/{run_id}` streams SSE events to the browser |
| 8.2 | SSE event pipeline | `app.py` | Parses agent stdout line-by-line; emits `phase_start`, `phase_done`, `phase_paused`, `awaiting_send`, `result`, `fatal` events |
| 8.3 | In-process fallback | `app.py` | When Windows policy blocks subprocess creation, runs the pipeline in-process via `asyncio.to_thread` |
| 8.4 | Email send endpoint | `app.py` | POST `/send_email_direct` — uses Gmail REST API (HTTPS) when `GMAIL_REFRESH_TOKEN` is set; falls back to SMTP for local dev |
| 8.5 | Dashboard UI | `index.html` | Real-time pipeline flow cards, terminal log panel, Analysis Results with themes + inline email preview + Send button |
| 8.6 | Windows compatibility | `app.py` | `WindowsProactorEventLoopPolicy` set at startup; `PYTHONIOENCODING=utf-8` injected into subprocess env |

### Exit Criteria
- Browser shows live phase progress as the agent runs.
- Analysis Results panel shows themes, review count, Google Doc link.
- Send Email button triggers email via Gmail API; confirmation shown inline.
- Falls back to in-process execution when subprocess is blocked.

---

## Phase 9 — Deployment
**Goal**: Package and ship the portal to a public cloud host.

### Tasks
| # | Task | File(s) | Details |
|---|------|---------|---------|
| 9.1 | Dockerfile | `Dockerfile` | `python:3.11-slim` base; pre-bakes `all-MiniLM-L6-v2` model to avoid cold-start network calls; exposes port 7860 (HuggingFace Spaces default) |
| 9.2 | Entrypoint script | `entrypoint.sh` | Decodes `GOOGLE_CREDENTIALS_BASE64` env var into `credentials.json` at container startup; launches uvicorn |
| 9.3 | HF Spaces config | `README.md` (YAML frontmatter) | `sdk: docker`, `app_port: 7860` — consumed by HuggingFace Spaces to configure the container |
| 9.4 | Token generation | `scripts/get_gmail_token.py` | One-time local script to perform Gmail OAuth2 flow and print `GMAIL_REFRESH_TOKEN` for HF Spaces secrets |
| 9.5 | Railway config | `railway.toml` | Alternative deployment target; health check + restart policy |

### Exit Criteria
- Docker image builds cleanly with model pre-baked.
- Portal accessible at public HuggingFace Spaces URL.
- All 6 pipeline phases complete end-to-end on HF Spaces.
- Email sends via Gmail REST API (not SMTP, which is blocked on HF Spaces).

---

## Dependency Graph

```mermaid
graph LR
    P0[Phase 0: Foundations] --> P1[Phase 1: Ingestion]
    P0 --> P2[Phase 2: Clustering]
    P0 --> P3[Phase 3: Summarization]
    P0 --> P4[Phase 4: Renderer]
    P0 --> P5[Phase 5: Docs MCP]
    P0 --> P6[Phase 6: Gmail MCP]
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> P5
    P5 --> P6
    P1 --> P7[Phase 7: Orchestration]
    P2 --> P7
    P3 --> P7
    P4 --> P7
    P5 --> P7
    P6 --> P7
    P7 --> P8[Phase 8: Portal]
    P8 --> P9[Phase 9: Deployment]
```

---

## Timeline Estimate

| Phase | Duration | Depends On |
|-------|----------|------------|
| 0 — Foundations | 3 days | — |
| 1 — Ingestion | 4 days | Phase 0 |
| 2 — Clustering | 3 days | Phase 0, 1 |
| 3 — Summarization | 4 days | Phase 0, 2 |
| 4 — Renderer | 2 days | Phase 0, 3 |
| 5 — Docs MCP | 3 days | Phase 0, 4 |
| 6 — Gmail MCP | 2 days | Phase 0, 5 |
| 7 — Orchestration | 4 days | All above |
| 8 — Portal | 3 days | Phase 7 |
| 9 — Deployment | 2 days | Phase 8 |
| **Total** | **~30 days** | |

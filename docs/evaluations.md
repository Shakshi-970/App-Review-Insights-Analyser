# Evaluations — Weekly Product Review Pulse AI Agent

This document defines success metrics, test strategies, and acceptance criteria for each implementation phase.

---

## Phase 0 — Foundations

| ID | Metric | Target | Test Method |
|----|--------|--------|-------------|
| E0.1 | Model serialization | All models round-trip JSON without data loss | Unit test: create instance → `.model_dump_json()` → parse back → assert equal |
| E0.2 | Config loading | Settings populate from `.env` and fallback to defaults | Unit test: set env vars → instantiate `Settings` → assert values |
| E0.3 | Run log CRUD | Create, read, update, check-exists all work | Unit test: in-memory SQLite → insert record → query → update status → verify |
| E0.4 | Idempotency query | `exists(product, iso_week)` returns correct boolean | Unit test: insert a success record → assert `exists()` returns True for same key, False for different key |

---

## Phase 1 — Ingestion

| ID | Metric | Target | Test Method |
|----|--------|--------|-------------|
| E1.1 | RSS parsing accuracy | 100% fields extracted from valid XML | Unit test: parse a saved sample RSS XML → assert all fields present |
| E1.2 | Play Store parsing | ≥95% reviews extracted from sample pages | Unit test: parse saved HTML → assert review count ≥ expected |
| E1.3 | PII scrubbing recall | 100% for emails, phones, 10-digit IDs | Unit test: run scrubber on 20 synthetic strings → assert all PII removed |
| E1.4 | PII scrubbing precision | ≤5% false positives on clean text | Unit test: run scrubber on 20 clean strings → assert ≤1 false positive |
| E1.5 | Deduplication | 0 duplicate `review_id` in output | Unit test: feed 10 reviews with 3 duplicates → assert output has 7 |
| E1.6 | Window filtering | Only reviews within N weeks returned | Unit test: feed reviews spanning 20 weeks → assert only last 12 returned |
| E1.7 | Scraping latency | <30s for 200 reviews per store | Timed integration test |

---

## Phase 2 — Clustering

| ID | Metric | Target | Test Method |
|----|--------|--------|-------------|
| E2.1 | Embedding dimensions | Output shape = (n_reviews, 384) for MiniLM | Unit test: embed 10 strings → assert shape |
| E2.2 | Cluster count | ≥2 clusters for ≥50 diverse reviews | Integration test with synthetic review set |
| E2.3 | Noise ratio | ≤30% of reviews in noise cluster (-1) | Integration test: assert `len(noise) / len(total) ≤ 0.3` |
| E2.4 | Representative selection | Each cluster has ≤10 centroid reviews | Unit test: assert `len(centroid_indices) ≤ 10` per cluster |
| E2.5 | Execution time | <60s for 500 reviews | Timed integration test |
| E2.6 | Determinism | Same input → same clusters (with fixed seed) | Run twice with same data → assert cluster assignments match |

---

## Phase 3 — Summarization

| ID | Metric | Target | Test Method |
|----|--------|--------|-------------|
| E3.1 | Quote grounding | 100% of quotes exist verbatim in source reviews | Unit test: validator rejects fabricated quote, accepts real quote |
| E3.2 | JSON validity | LLM output parses into `List[Theme]` | Integration test: call LLM → parse response → assert no validation error |
| E3.3 | Theme count | 1 theme per cluster (matching cluster count) | Assert `len(themes) == len(clusters)` |
| E3.4 | Action ideas | 1-2 per theme, non-empty strings | Assert `1 ≤ len(theme.action_ideas) ≤ 2` for each theme |
| E3.5 | Token budget | Run stays within configured limit | Integration test: mock high-token response → assert abort triggered |
| E3.6 | Tone compliance | Themes and actions are professional, not sarcastic | Manual review of 5 sample outputs |

---

## Phase 4 — Renderer

| ID | Metric | Target | Test Method |
|----|--------|--------|-------------|
| E4.1 | Markdown structure | Contains H2 heading, theme sections, blockquotes | Unit test: parse output Markdown → assert heading, `>` blocks present |
| E4.2 | Heading anchor stability | Same `(product, iso_week)` always produces same anchor | Unit test: call twice → assert anchors equal |
| E4.3 | Email HTML validity | No broken tags; renders in browser | Unit test: parse with html.parser → assert no errors |
| E4.4 | Deep-link placeholder | Email contains `{{DOC_LINK}}` placeholder | Unit test: assert placeholder string present |
| E4.5 | Report completeness | All themes, quotes, and actions present in rendered output | Unit test: render a known `PulseReport` → assert every theme name appears |

---

## Phase 5 — Google Docs MCP

| ID | Metric | Target | Test Method |
|----|--------|--------|-------------|
| E5.1 | MCP connection | Client connects and lists tools | Integration test: connect → `list_tools()` → assert ≥1 tool |
| E5.2 | Append success | Section appears in target Doc | Integration test: append → read Doc → assert heading present |
| E5.3 | Idempotency | Duplicate append is a no-op | Integration test: append twice → assert only 1 section |
| E5.4 | Deep-link retrieval | Returns a valid `https://docs.google.com/...` URL | Assert URL matches expected pattern |
| E5.5 | Error handling | Graceful failure on auth error or missing Doc | Integration test: use invalid Doc ID → assert clean error, no crash |

---

## Phase 6 — Gmail MCP

| ID | Metric | Target | Test Method |
|----|--------|--------|-------------|
| E6.1 | MCP connection | Client connects and lists tools | Integration test: connect → `list_tools()` → assert ≥1 tool |
| E6.2 | Draft creation | Draft appears in Gmail with correct subject | Integration test: create draft → verify in Gmail UI |
| E6.3 | Deep-link insertion | Email body contains the Doc heading URL (not placeholder) | Assert `{{DOC_LINK}}` is replaced with actual URL |
| E6.4 | Idempotency | No duplicate email for same `(product, iso_week)` | Integration test: run twice → assert only 1 message_id in run_log |
| E6.5 | Staging vs Production | Default to draft; send only if `SEND_MODE=production` | Unit test: mock config → assert draft vs send path taken |

---

## Phase 7 — Orchestration

| ID | Metric | Target | Test Method |
|----|--------|--------|-------------|
| E7.1 | Tool discovery | Agent lists all 6 registered tools | Unit test: register all → assert `len(tools) == 6` |
| E7.2 | Correct tool selection | Agent picks `ingestion_tool` when asked to "fetch reviews" | Integration test with Groq: prompt → assert tool call name |
| E7.3 | End-to-end run | Full pipeline completes for 1 product + 1 week | Integration test: run agent → assert `run_log` has success record |
| E7.4 | Idempotent re-run | Second run for same key is a no-op | Run twice → assert run_log shows `skipped` for second |
| E7.5 | Error recovery | Agent retries on transient MCP timeout | Mock MCP to fail once → assert retry succeeds |
| E7.6 | CLI interface | `--product` and `--week` flags work | Subprocess test: call with args → assert exit code 0 |
| E7.7 | Backfill mode | Processes all missing weeks in window | Mock run_log with gaps → run backfill → assert gaps filled |
| E7.8 | Audit completeness | Every tool call logged with timestamp and hashes | After run → query run_log → assert all steps recorded |

Excited to share my submission for the App Review Insights Analyser — an end-to-end AI agent that turns raw app store reviews into a weekly product pulse, automatically.

**The problem it solves:**
Product and growth teams drown in thousands of Play Store and App Store reviews every week. There's signal in there — but no time to read it. I built an autonomous agent that does it for them: scrape → cluster → summarize → deliver.

**What it does (end to end):**
- Imports the last 104 weeks of reviews from both App Store and Play Store
- Groups them into themes using semantic clustering (no manual tagging)
- Generates a one-page weekly note: top themes, real user quotes, 3 action ideas
- Appends the report to a shared Google Doc
- Sends a formatted teaser email — automatically, every week

**Tech stack & why:**

🔵 **Groq + Llama-3.3-70b-versatile** — Ultra-fast inference for summarization and the orchestration agent loop. Tool-calling API lets the LLM decide which pipeline step to run next.

🟢 **sentence-transformers (all-MiniLM-L6-v2)** — Lightweight, accurate embeddings for 1,800+ reviews in seconds. No GPU needed.

📐 **UMAP + HDBSCAN** — Density-based clustering that finds natural theme boundaries without forcing a fixed number of clusters. Noise reviews are automatically filtered.

🔌 **FastMCP (Model Context Protocol)** — Built custom MCP servers for Google Docs and Gmail. The agent calls them as tools — clean separation between reasoning and execution.

☁️ **HuggingFace Spaces** — Free Docker hosting for the Docs MCP server. No credit card required.

🗃️ **SQLite run log** — Every run is logged with token usage, delivery IDs, and status. Idempotent by design — re-running the same week is always a no-op.

**Deliverables shipped:**
✅ Deployed MCP server on HuggingFace Spaces
✅ Live Google Doc with the Groww 2026-W17 pulse report
✅ Email teaser delivered to inbox (Gmail SMTP via MCP)
✅ Reviews CSV — 1,818 Groww reviews, PII-scrubbed
✅ README with one-command re-run and theme legend

**What I learned:**
Clustering beats prompting for theme discovery. Asking an LLM to "find 5 themes in 1,800 reviews" in one shot is expensive and inconsistent. Embedding → UMAP → HDBSCAN → LLM-per-cluster is faster, cheaper, and more grounded — every quote is substring-validated against the source.

GitHub → https://github.com/Shakshi-970/App-Review-Insights-Analyser

#AI #LLM #MCP #ProductManagement #MachineLearning #Groq #HuggingFace #Python #GenerativeAI #AIAgents

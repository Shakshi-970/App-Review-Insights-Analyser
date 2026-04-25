[X/5] — PM Fellowship Challenge | App Review Insights Analyser

I used to wonder how PMs at companies like Groww actually know what's frustrating users.

Do they read every review? That's 1,800+ reviews a week just for one app.
Do they rely on support tickets? Those only catch the loudest complaints.

So I built something to do it automatically.

---

Here's what the agent does every week — without me touching anything:

1. Pulls the latest Play Store + App Store reviews for Groww
2. Groups them into themes based on what users are *actually* talking about — not what I assume they're talking about
3. Writes a one-page pulse: top themes, real quotes, 3 action ideas
4. Drops the report into a Google Doc
5. Sends me a formatted email with a link to the full report

No manual work. No copy-pasting. Just a clean weekly brief, ready Monday morning.

---

The part that surprised me most?

I thought I could just ask the AI: *"Find me 5 themes in these 1,800 reviews."*

That didn't work well. The LLM kept hallucinating themes and making up quotes.

The fix was to first *cluster* the reviews mathematically (grouping similar reviews together using embeddings + UMAP + HDBSCAN), and then ask the LLM to summarize *each cluster* separately. Every quote in the final report is substring-matched against the actual review — so nothing is made up.

Lesson: Use AI to summarize. Use math to group.

---

Tech I used (and why):

→ **Groq + Llama 3** — fast enough to process all clusters in under a minute
→ **sentence-transformers** — converts reviews into vectors so similar complaints group together
→ **UMAP + HDBSCAN** — finds natural clusters without me pre-defining categories
→ **FastMCP** — lets the AI agent "talk to" Google Docs and Gmail like tools
→ **HuggingFace Spaces** — free cloud hosting, no credit card needed

---

What this means for a PM:

Instead of spending 2 hours reading reviews on Sunday night, you get a structured brief that tells you exactly what to bring up in Monday's standup.

That's the real value — not the tech, but the time it gives back.

---

GitHub → https://github.com/Shakshi-970/App-Review-Insights-Analyser

Grateful to be learning this as part of the @NextLeap PM Fellowship — the projects here are genuinely making me think differently about AI in product work.

#NextLeapPMFellowship #AI #ProductManagement #GenerativeAI #LLM #AIAgents #MCP #Groq #Python

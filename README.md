# Weekly Product Review Pulse AI Agent

An autonomous AI Agent that scrapes, clusters, and summarizes app store reviews, delivering insights via Google Docs and Gmail using the Model Context Protocol (MCP).

## Project Structure

The project is divided into 8 distinct phases:

- `src/phase0_foundations/`: Data models, configuration, and run logging.
- `src/phase1_ingestion/`: App Store and Play Store review scrapers + PII scrubbing.
- `src/phase2_clustering/`: Embedding and density-based clustering (UMAP + HDBSCAN).
- `src/phase3_summarization/`: LLM-based theme generation and quote validation.
- `src/phase4_renderer/`: Markdown and HTML report rendering.
- `src/phase5_docs_mcp/`: Google Docs delivery via MCP.
- `src/phase6_gmail_mcp/`: Gmail notification via MCP.
- `src/phase7_orchestration/`: AI Agent loop and tool registry.

## Documentation

Detailed documentation can be found in the `docs/` folder:
- `problemStatement.md`: Project goals and requirements.
- `architecture.md`: System design and data flow.
- `implementationPlan.md`: Phase-wise task breakdown.
- `evaluations.md`: Metrics and test strategies.
- `edge_cases.md`: Failure modes and mitigations.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   - Copy `.env.example` to `.env`.
   - Add your `GROQ_API_KEY`.

3. **Run Tests**:
   ```bash
   python -m unittest tests/test_foundations.py
   ```

## Usage

(Implementation in progress)

"""Groq-compatible tool schemas for the Phase 7 agent loop."""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "scrape_reviews",
            "description": (
                "Fetch and clean reviews from App Store and Play Store "
                "for the given product and ISO week."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product": {
                        "type": "string",
                        "description": "Product name, e.g. 'Groww'"
                    },
                    "iso_week": {
                        "type": "string",
                        "description": "ISO week string, e.g. '2026-W17'"
                    }
                },
                "required": ["product", "iso_week"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cluster_reviews",
            "description": (
                "Embed the scraped reviews using sentence-transformers and "
                "cluster them into thematic groups with UMAP + HDBSCAN."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_clusters",
            "description": (
                "Use the LLM to summarize each cluster into a named theme "
                "with validated verbatim quotes and action ideas."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "render_report",
            "description": (
                "Convert the themes into a structured PulseReport and render "
                "it to Markdown (for Google Docs) and HTML (for email)."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "publish_to_docs",
            "description": (
                "Append the rendered report to the team Google Doc via MCP. "
                "Idempotent — skips if the week's heading anchor is already present. "
                "Returns the deep-link URL."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": (
                "Send the HTML teaser email to the configured recipient via Gmail MCP, "
                "embedding the Google Doc deep-link in the CTA button."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
import shlex
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.phase0_foundations.config import settings
from src.phase0_foundations.models import PulseReport

logger = logging.getLogger(__name__)


class DocsClient:
    """
    MCP client for Google Docs.  Uses PulseDocFormatter for visually
    designed output instead of markdown parsing.

    Transport selection (automatic):
    - If GOOGLE_DOCS_MCP_SERVER_URL is set in .env → SSE (deployed server)
    - Otherwise                                     → stdio (local subprocess)
    """

    def __init__(self):
        self._url = settings.GOOGLE_DOCS_MCP_SERVER_URL.strip()
        if not self._url:
            cmd_parts = shlex.split(settings.GOOGLE_DOCS_MCP_SERVER_COMMAND)
            self._stdio_params = StdioServerParameters(
                command=cmd_parts[0],
                args=cmd_parts[1:],
                env=None,
            )

    @asynccontextmanager
    async def _session(self):
        """Yield an initialised MCP ClientSession using the right transport."""
        if self._url:
            from mcp.client.sse import sse_client
            async with sse_client(self._url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        else:
            async with stdio_client(self._stdio_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

    # ── public sync API ───────────────────────────────────────────────────────

    def run_clear_document(self, document_id: str) -> Dict[str, Any]:
        return asyncio.run(self._clear_document(document_id))

    def run_append_report(self, document_id: str, report: PulseReport,
                          anchor: str) -> Dict[str, Any]:
        return asyncio.run(self._append_report(document_id, report, anchor))

    # ── async internals ───────────────────────────────────────────────────────

    async def _clear_document(self, document_id: str) -> Dict[str, Any]:
        async with self._session() as session:
            result = await session.call_tool(
                "docs_clear_document", {"document_id": document_id}
            )
            if hasattr(result, 'content') and result.content:
                try:
                    return json.loads(result.content[0].text)
                except Exception:
                    pass
            return {"status": "success"}

    async def _append_report(self, document_id: str, report: PulseReport,
                             anchor: str) -> Dict[str, Any]:
        async with self._session() as session:
            # Idempotency: skip if anchor already present
            doc_content = await session.call_tool(
                "docs_get_document", {"document_id": document_id}
            )
            if anchor in str(doc_content):
                logger.info("Anchor %s already present — skipping.", anchor)
                return {"status": "skipped", "document_id": document_id}

            # Build visually designed requests via PulseDocFormatter
            from src.phase5_docs_mcp.pulse_formatter import PulseDocFormatter
            requests = PulseDocFormatter(start_index=1).format(report)

            raw = await session.call_tool("docs_batch_update", {
                "document_id": document_id,
                "requests": requests,
            })

            # Parse result (MCP wraps it in .content[0].text)
            update_result: dict = {}
            if hasattr(raw, 'content') and raw.content:
                try:
                    update_result = json.loads(raw.content[0].text)
                except Exception:
                    update_result = {"raw": str(raw)}

            # Surface any API error so the runner can report it
            if isinstance(update_result, dict) and update_result.get("status") == "error":
                return {
                    "status": "error",
                    "document_id": document_id,
                    "detail": update_result.get("message", str(update_result)),
                }

            doc_url = (
                f"https://docs.google.com/document/d/{document_id}"
                f"#pulse-{report.product.lower()}-{report.iso_week.lower()}"
            )
            return {"status": "success", "document_id": document_id, "doc_url": doc_url}

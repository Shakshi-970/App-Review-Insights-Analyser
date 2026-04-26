import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any
import shlex
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.phase0_foundations.config import settings


class GmailClient:
    """
    Client for interacting with Gmail via MCP.

    Transport selection (automatic):
    - If GMAIL_MCP_SERVER_URL is set in .env → SSE (deployed server)
    - Otherwise                               → stdio (local subprocess)
    """

    def __init__(self):
        self._url = settings.GMAIL_MCP_SERVER_URL.strip()
        if not self._url:
            cmd_parts = shlex.split(settings.GMAIL_MCP_SERVER_COMMAND)
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

    async def send_teaser(self, recipient: str, subject: str, html_content: str) -> Dict[str, Any]:
        """Sends or drafts a teaser email via Gmail MCP."""
        async with self._session() as session:
            tool_name = (
                "gmail_send_message"
                if settings.SEND_MODE == "production"
                else "gmail_create_draft"
            )
            params = {"to": recipient, "subject": subject, "body": html_content}
            result = await session.call_tool(tool_name, params)
            # Parse actual tool result — don't swallow errors
            if hasattr(result, 'content') and result.content:
                import json as _json
                try:
                    tool_result = _json.loads(result.content[0].text)
                except Exception:
                    tool_result = {"status": "unknown", "raw": str(result.content[0].text)}
            else:
                tool_result = {"status": "unknown"}
            return tool_result

    def run_send_teaser(self, recipient: str, subject: str, html_content: str) -> Dict[str, Any]:
        """Synchronous wrapper for send_teaser with advanced error unwrapping."""
        try:
            return asyncio.run(self.send_teaser(recipient, subject, html_content))
        except Exception as e:
            # Handle Python 3.11+ ExceptionGroup (TaskGroup errors)
            error_msg = str(e)
            if hasattr(e, "exceptions") and e.exceptions:
                error_msg = f"{type(e.exceptions[0]).__name__}: {str(e.exceptions[0])}"
            
            import logging
            logging.error(f"Gmail Client Error: {error_msg}")
            return {"status": "error", "message": f"Gmail process crash: {error_msg}"}

import os
import base64
import json
import logging
import tempfile
from google.oauth2 import service_account
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("google-docs-mcp")

# MCP Server Definition
mcp = FastMCP("GoogleDocs")

# Resolve credentials: prefer base64 env var (cloud), fall back to file (local)
_HERE = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(_HERE, "..", "..", "credentials.json")

def _resolve_credentials_file() -> str:
    """Return a path to a valid service-account JSON file.
    In cloud deployments set GOOGLE_CREDENTIALS_BASE64 to the base64-encoded
    contents of credentials.json — no file needed in the container image.
    """
    b64 = os.getenv("GOOGLE_CREDENTIALS_BASE64", "")
    if b64:
        data = base64.b64decode(b64.encode())
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.write(data)
        tmp.flush()
        return tmp.name
    return CREDENTIALS_FILE

def get_docs_service():
    """Authenticates and returns the Google Docs service."""
    creds_file = _resolve_credentials_file()
    if not os.path.exists(creds_file):
        raise FileNotFoundError(
            f"'{creds_file}' not found. Provide credentials.json or set "
            "GOOGLE_CREDENTIALS_BASE64 env var."
        )
    scopes = ['https://www.googleapis.com/auth/documents']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=scopes)
    return build('docs', 'v1', credentials=creds)

@mcp.tool()
def docs_get_document(document_id: str) -> str:
    """
    Retrieves the full text content of a Google Document.
    """
    try:
        service = get_docs_service()
        doc = service.documents().get(documentId=document_id).execute()
        
        # Extract text from structural elements
        text = ""
        for content in doc.get('body').get('content'):
            if 'paragraph' in content:
                for element in content.get('paragraph').get('elements'):
                    if 'textRun' in element:
                        text += element.get('textRun').get('content')
        return text
    except Exception as e:
        logger.error(f"Error fetching document {document_id}: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def docs_batch_update(document_id: str, requests: list) -> dict:
    """
    Executes a batch of updates on a Google Document.
    """
    try:
        service = get_docs_service()
        result = service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests}
        ).execute()
        return result
    except Exception as e:
        logger.error(f"Error updating document {document_id}: {e}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
def docs_clear_document(document_id: str) -> dict:
    """
    Clears all content from a Google Document.
    """
    try:
        service = get_docs_service()
        doc = service.documents().get(documentId=document_id).execute()
        end_index = 0
        for content in doc.get('body').get('content'):
            end_index = max(end_index, content.get('endIndex', 0))
        
        logger.info(f"Clearing document {document_id}. End index: {end_index}")
        
        if end_index <= 2: 
            return {"status": "success", "message": "Already empty"}

        # Delete from index 1 to end_index - 1
        requests = [{
            'deleteContentRange': {
                'range': {
                    'startIndex': 1,
                    'endIndex': end_index - 1
                }
            }
        }]
        
        result = service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests}
        ).execute()
        return {"status": "success", "result": result}
    except Exception as e:
        logger.exception(f"Failed to clear document {document_id}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Google Docs MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                        help="Transport mode: stdio (local) or sse (deployed)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)),
                        help="HTTP port for SSE transport (default: $PORT or 8000)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Host for SSE transport (default: 0.0.0.0)")
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        logger.info("Starting Google Docs MCP server (SSE) on %s:%d", args.host, args.port)
        mcp.run(transport="sse")
    else:
        logger.info("Starting Google Docs MCP server (stdio)")
        mcp.run()

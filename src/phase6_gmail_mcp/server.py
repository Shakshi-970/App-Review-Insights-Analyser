import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings
from dotenv import load_dotenv

# Load env for testing standalone
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gmail-mcp")

# DNS rebinding protection disabled — server runs behind HF/cloud reverse proxy
mcp = FastMCP("GmailSMTP", transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))

# Settings from Env
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "sshakshi970@gmail.com")
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

@mcp.tool()
def gmail_send_message(to: str, subject: str, body: str) -> dict:
    """
    Sends an email via Gmail SMTP using an App Password.
    """
    if not APP_PASSWORD:
        return {"status": "error", "message": "GMAIL_APP_PASSWORD not found in .env"}

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        # Connect and Send
        logger.info(f"Connecting to Gmail SMTP. From: {SENDER_EMAIL} To: {to}")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
            
        logger.info("Email sent successfully!")
        return {"status": "sent", "to": to, "subject": subject}
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
def gmail_create_draft(to: str, subject: str, body: str) -> dict:
    """
    SMTP doesn't support drafts directly. This tool will just send the email 
    in this implementation, or you can use it to 'log' the intent.
    """
    return gmail_send_message(to, f"[DRAFT] {subject}", body)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gmail MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                        help="Transport mode: stdio (local) or sse (deployed)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8001)),
                        help="HTTP port for SSE transport (default: $PORT or 8001)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Host for SSE transport (default: 0.0.0.0)")
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        logger.info("Starting Gmail MCP server (SSE) on %s:%d", args.host, args.port)
        mcp.run(transport="sse")
    else:
        logger.info("Starting Gmail MCP server (stdio)")
        mcp.run()

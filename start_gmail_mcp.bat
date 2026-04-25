@echo off
cd /d "c:\Users\shakshi.d.singh\OneDrive - Accenture\M3"
python src\phase6_gmail_mcp\server.py --transport sse --port 8001 --host 0.0.0.0 >> logs\gmail_mcp.log 2>> logs\gmail_mcp_err.log

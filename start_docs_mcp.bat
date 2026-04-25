@echo off
cd /d "c:\Users\shakshi.d.singh\OneDrive - Accenture\M3"
python src\phase5_docs_mcp\server.py --transport sse --port 8000 --host 0.0.0.0 >> logs\docs_mcp.log 2>> logs\docs_mcp_err.log

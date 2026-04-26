"""
Pulse Agent Demo Portal — FastAPI + SSE backend.

Run:
    PYTHONPATH=. uvicorn src.portal.app:app --host 0.0.0.0 --port 8080
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

# Windows requires ProactorEventLoop for asyncio subprocess support.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI(title="Pulse Agent Portal")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_queues: dict[str, asyncio.Queue] = {}

_PHASE_MAP = {
    "[1/6]": "scrape",
    "[2/6]": "cluster",
    "[3/6]": "summarize",
    "[4/6]": "render",
    "[5/6]": "docs",
    "[6/6]": "email",
}

# Real results are now parsed from the agent's stdout [RESULT_JSON] prefix
_DEMO_THEMES = []



@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse((Path(__file__).parent / "index.html").read_text(encoding="utf-8"))


@app.post("/run")
async def start_run(request: Request):
    body = await request.json()
    product = body.get("product", "Groww")
    week    = body.get("week", "2026-W17")

    run_id = str(uuid.uuid4())[:8]
    queue: asyncio.Queue = asyncio.Queue()
    _queues[run_id] = queue

    asyncio.create_task(_run_pipeline(run_id, product, week, queue))
    return {"run_id": run_id}


@app.get("/stream/{run_id}")
async def stream_events(run_id: str):
    queue = _queues.get(run_id)
    if not queue:
        return StreamingResponse(iter([]), media_type="text/event-stream")

    async def generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300)
            except asyncio.TimeoutError:
                yield 'data: {"type":"ping"}\n\n'
                continue
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in ("done", "fatal"):
                break

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


from pydantic import BaseModel
from src.phase0_foundations.config import settings

class EmailRequest(BaseModel):
    subject: str
    html: str

def _send_via_gmail_api(sender: str, recipient: str, subject: str, html: str):
    """Send via Gmail REST API (HTTPS/443) — works on HF Spaces where SMTP is blocked."""
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=settings.GMAIL_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    creds.refresh(Request())

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service = build("gmail", "v1", credentials=creds)
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


@app.post("/send_email_direct")
async def send_email_direct(req: EmailRequest):
    """
    Send the email — uses Gmail API (HTTPS) when OAuth2 creds are set,
    falls back to SMTP for local dev. Called by the Send Email button in the UI.
    """
    recipient = settings.RECIPIENT_EMAIL
    if not recipient:
        return {"status": "error", "message": "RECIPIENT_EMAIL not set"}

    sender = settings.SENDER_EMAIL
    if not sender:
        return {"status": "error", "message": "SENDER_EMAIL not set"}

    # ── Gmail API path (HF Spaces / any SMTP-blocked host) ────────────────────
    if settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET and settings.GMAIL_REFRESH_TOKEN:
        try:
            await asyncio.to_thread(
                _send_via_gmail_api, sender, recipient, req.subject, req.html
            )
            return {"status": "ok", "message": f"Email sent to {recipient}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"Gmail API error: {str(e)}"}

    # ── SMTP fallback (local dev) ──────────────────────────────────────────────
    app_password = settings.GMAIL_APP_PASSWORD
    if not app_password:
        return {"status": "error", "message": "Set GMAIL_REFRESH_TOKEN+CLIENT_ID+CLIENT_SECRET (or GMAIL_APP_PASSWORD for local dev)"}

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = req.subject
        msg.attach(MIMEText(req.html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender, app_password)
            server.send_message(msg)

        return {"status": "ok", "message": f"Email sent to {recipient}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"SMTP error: {str(e)}"}

async def _run_pipeline(run_id: str, product: str, week: str, queue: asyncio.Queue):
    import traceback
    loop = asyncio.get_running_loop()

    def emit(e):
        # Safe to call from worker threads too (in-proc fallback path).
        loop.call_soon_threadsafe(queue.put_nowait, e)
    try:
        await _live_pipeline(product, week, emit)
    except Exception as exc:
        tb = traceback.format_exc()
        for line in tb.splitlines():
            if line.strip():
                emit({"type": "log", "message": line})
        emit({"type": "fatal", "message": str(exc) or repr(exc) or "Unknown error (see log above)"})
    finally:
        emit({"type": "done"})
        await asyncio.sleep(120)
        _queues.pop(run_id, None)

# ── LIVE PIPELINE ──────────────────────────────────────────────────────────────

async def _live_pipeline(product: str, week: str, emit):
    """Runs the agent as a subprocess; captures stdout line-by-line.
    Falls back to in-process execution if subprocess creation is blocked."""
    project_root = Path(__file__).parent.parent.parent
    cmd = [
        sys.executable, "-B", "-u", "-m", "src.phase7_orchestration.agent",
        "--product", product, "--week", week, "--force", "--clear-doc", "--pause-email"
    ]
    sub_env = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        # Don't inherit broken local proxy settings into the agent subprocess.
        "HTTP_PROXY": "",  "HTTPS_PROXY": "",  "ALL_PROXY": "",
        "http_proxy": "", "https_proxy": "", "all_proxy": "",
        # Use cached HuggingFace models only — prevents httpx revision-check
        # calls that fail in corporate networks with proxy cleared.
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        # Force UTF-8 stdout/stderr in the subprocess — Windows pipes
        # default to CP1252 which chokes on Unicode characters in logs.
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(project_root),
            env=sub_env,
        )
    except (OSError, NotImplementedError) as e:
        # OSError winerror=5: Windows policy blocks subprocess from server process.
        # NotImplementedError: asyncio subprocess needs ProactorEventLoop on Windows.
        emit({"type": "log", "message": f"[portal] subprocess blocked ({type(e).__name__}: {e}) — running in-process"})
        await asyncio.to_thread(_run_pipeline_inproc, product, week, emit)
        return

    current_phase: list[str | None] = [None]

    async for raw in proc.stdout:
        msg = raw.decode(errors="replace").rstrip()
        if not msg:
            continue

        if msg.strip().startswith("[RESULT_JSON]"):
            try:
                json_str = msg.strip().replace("[RESULT_JSON] ", "")
                result_data = json.loads(json_str)
                emit(result_data)
                continue
            except Exception as e:
                emit({"type": "log", "message": f"Error parsing result: {e}"})

        # Detect phase transitions from [N/6] prefixes
        for prefix, phase in _PHASE_MAP.items():
            if msg.strip().startswith(prefix):
                if current_phase[0] and current_phase[0] != phase:
                    emit({"type": "phase_done", "phase": current_phase[0], "data": {}})
                current_phase[0] = phase
                emit({"type": "phase_start", "phase": phase})
                break

        # Detect email paused — do NOT mark email step as done
        if "--pause-email flag set" in msg and current_phase[0] == "email":
            emit({"type": "phase_paused", "phase": "email", "data": {}})
            # Reset current_phase so "completed successfully" won't mark email done
            current_phase[0] = None

        # Only mark phase done on "completed successfully" if we have an active phase
        # (email phase was already reset to None above when paused)
        elif "completed successfully" in msg and current_phase[0]:
            emit({"type": "phase_done", "phase": current_phase[0], "data": {}})

        # Detect the "awaiting email approval" message — emit special event
        if "awaiting email approval" in msg:
            emit({"type": "awaiting_send"})

        emit({"type": "log", "message": msg})

    await proc.wait()

    if proc.returncode != 0:
        emit({"type": "fatal", "message": f"Agent process exited with code {proc.returncode}"})


def _run_pipeline_inproc(product: str, week: str, emit):
    """
    In-process pipeline runner used when Windows policy blocks subprocess creation.
    Emits the same event types as the subprocess-driven path.
    """
    import traceback
    from datetime import datetime
    import contextlib
    import io
    import sys

    # Set HF offline mode for this process so sentence-transformers doesn't
    # make network calls when running in-process (subprocess path sets these
    # as env vars; here we set them directly since we're in the same process).
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    from src.phase0_foundations.models import RunRecord
    from src.phase0_foundations.run_log import RunLog
    from src.phase7_orchestration.agent import ProductReviewAgent

    agent = ProductReviewAgent(clear_doc=True, pause_email=True)
    run_log = RunLog()

    run_id = str(uuid.uuid4())
    run_record = RunRecord(
        run_id=run_id,
        product=product,
        iso_week=week,
        status="failed",
        started_at=datetime.now(),
    )
    run_log.create_run(run_record)

    tool_to_phase = {
        "scrape_reviews": "scrape",
        "cluster_reviews": "cluster",
        "summarize_clusters": "summarize",
        "render_report": "render",
        "publish_to_docs": "docs",
        "send_email": "email",
    }

    pipeline = [
        ("scrape_reviews", {"product": product, "iso_week": week}),
        ("cluster_reviews", {}),
        ("summarize_clusters", {}),
        ("render_report", {}),
        ("publish_to_docs", {}),
        ("send_email", {}),
    ]

    class _EmitWriter(io.TextIOBase):
        def __init__(self, emit_fn):
            self._emit = emit_fn
            self._buf = ""

        def write(self, s):
            if not s:
                return 0
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                line = line.rstrip("\r")
                if line:
                    self._emit({"type": "log", "message": line})
            return len(s)

        def flush(self):
            if self._buf.strip():
                self._emit({"type": "log", "message": self._buf.strip()})
            self._buf = ""

    out = _EmitWriter(emit)

    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            for tool_name, args in pipeline:
                phase = tool_to_phase[tool_name]
                emit({"type": "phase_start", "phase": phase})
                result = agent._with_retry(agent._execute_tool, tool_name, args, run_record)

                if result.get("status") == "error":
                    raise RuntimeError(result.get("message", str(result)))

                if tool_name == "send_email" and result.get("status") == "paused":
                    emit({"type": "phase_paused", "phase": "email", "data": result})
                    emit({"type": "awaiting_send"})
                else:
                    emit({"type": "phase_done", "phase": phase, "data": result})

            # Emit final result payload (mirrors agent's [RESULT_JSON] output)
            result_data = {
                "type": "result",
                "product": product,
                "week": week,
                "review_count": run_record.review_count,
                "token_usage": run_record.token_usage,
                "doc_url": agent._state.get("doc_url"),
                "email_html": agent._state.get("email_html"),
                "email_subject": agent._state.get("email_subject"),
                "themes": [t.model_dump() for t in agent._state.get("themes", [])],
            }
            emit(result_data)

            run_record.status = "pending_email"
            run_record.completed_at = datetime.now()
            run_record.token_usage = getattr(agent.synthesizer, "total_tokens_used", run_record.token_usage)
    except Exception as exc:
        tb = traceback.format_exc()
        for line in tb.splitlines():
            if line.strip():
                emit({"type": "log", "message": line})
        emit({"type": "fatal", "message": str(exc) or repr(exc) or "Unknown error (see log above)"})
        run_record.status = "failed"
        raise
    finally:
        run_log.update_run(run_record)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.portal.app:app", host="0.0.0.0", port=8080, reload=False)

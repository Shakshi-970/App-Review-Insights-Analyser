from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # LLM Settings
    GROQ_API_KEY: str = ""
    DEFAULT_MODEL: str = "llama-3.1-8b-instant"
    
    # Ingestion Settings
    SUPPORTED_PRODUCTS: List[str] = ["INDMoney", "Groww", "PowerUp Money", "Wealth Monitor", "Kuvera"]
    APP_STORE_IDS: dict = {
        "INDMoney": "1459345244",
        "Groww": "1404115162",
        "PowerUp Money": "1642232148",
        "Wealth Monitor": "1517406253",
        "Kuvera": "1335017173"
    }
    PLAY_STORE_IDS: dict = {
        "INDMoney": "com.indwealth",
        "Groww": "com.nextbillion.groww",
        "PowerUp Money": "com.powerupmoney",
        "Wealth Monitor": "com.wealthmonitor",
        "Kuvera": "com.kuvera.app"
    }
    ROLLING_WINDOW_WEEKS: int = 4
    MIN_REVIEW_LENGTH: int = 10
    MAX_REVIEW_LENGTH: int = 2000
    
    # MCP Settings — local stdio (used when *_URL is empty)
    GOOGLE_DOCS_MCP_SERVER_COMMAND: str = "python src/phase5_docs_mcp/server.py"
    GMAIL_MCP_SERVER_COMMAND: str = "python src/phase6_gmail_mcp/server.py"
    # MCP Settings — deployed SSE (set these to switch to remote servers)
    GOOGLE_DOCS_MCP_SERVER_URL: str = ""   # e.g. http://docs-mcp:8000/sse
    GMAIL_MCP_SERVER_URL: str = ""         # e.g. http://gmail-mcp:8001/sse
    
    # DB Settings
    DATABASE_URL: str = "sqlite:///run_log.db"
    
    # Operation Settings
    SEND_MODE: str = "staging"  # staging (draft) or production (send)
    REVIEWS_TO_SCRAPE: int = 2000
    CLUSTERING_SAMPLE_SIZE: int = 2000
    TOKEN_BUDGET_PER_RUN: int = 500000

    # Summarization performance knobs (Phase 3)
    SUMMARIZE_INTER_CALL_DELAY_S: float = 2.0
    SUMMARIZE_MAX_THEMES: int = 15
    SUMMARIZE_MAX_REP_REVIEWS: int = 4
    SUMMARIZE_MAX_REVIEW_CHARS: int = 180
    
    GOOGLE_DOCS_ID: str = ""
    RECIPIENT_EMAIL: str = ""
    SENDER_EMAIL: str = ""
    GMAIL_APP_PASSWORD: str = ""

    # Gmail API OAuth2 — preferred over SMTP (works on HF Spaces where SMTP is blocked)
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REFRESH_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

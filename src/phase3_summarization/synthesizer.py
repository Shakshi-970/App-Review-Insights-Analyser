import json
import time
from typing import List, Optional
from groq import Groq, RateLimitError

from src.phase0_foundations.config import settings
from src.phase0_foundations.models import Cluster, Theme
from src.phase3_summarization.prompts import SYSTEM_PROMPT, get_user_prompt
from src.phase3_summarization.quote_validator import QuoteValidator

# llama-3.1-8b-instant has a much higher TPM/RPM allowance on Groq free tier
_SYNTH_MODEL = "llama-3.1-8b-instant"
_INTER_CALL_DELAY = 2.0    # Reduced from 12.0 for faster execution
_MAX_THEMES = 15          # Cap themes to avoid 10-minute waits
_MAX_REPS = 4              # representative reviews sent per cluster
_MAX_REV_CHARS = 180       # truncate each review to keep prompt small


class Synthesizer:
    """
    Orchestrates the LLM summarization of clusters into themes.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = model_name or _SYNTH_MODEL
        self.validator = QuoteValidator()
        self.total_tokens_used = 0

    def synthesize_clusters(self, product_name: str, clusters: List[Cluster]) -> List[Theme]:
        """
        Processes each cluster and returns a list of validated Themes.
        """
        themes: List[Theme] = []
        self.total_tokens_used = 0

        inter_delay = float(getattr(settings, "SUMMARIZE_INTER_CALL_DELAY_S", _INTER_CALL_DELAY))
        max_themes = int(getattr(settings, "SUMMARIZE_MAX_THEMES", _MAX_THEMES))
        max_reps = int(getattr(settings, "SUMMARIZE_MAX_REP_REVIEWS", _MAX_REPS))
        max_rev_chars = int(getattr(settings, "SUMMARIZE_MAX_REVIEW_CHARS", _MAX_REV_CHARS))

        for i, cluster in enumerate(clusters):
            # Cap themes and check budget before processing next cluster
            if i >= max_themes:
                print(f"[*] Capping at {max_themes} themes for performance.")
                break
            if self.total_tokens_used >= settings.TOKEN_BUDGET_PER_RUN:
                print(f"[!] Token budget exceeded ({self.total_tokens_used} tokens). Stopping summarization.")
                break

            # Only summarize if there are enough reviews
            if not cluster.reviews:
                continue

            # Throttle between calls to avoid Groq 429s
            if i > 0:
                time.sleep(inter_delay)

            # Extract representative review texts — capped and truncated to limit tokens
            reps = [
                cluster.reviews[j].text[:max_rev_chars]
                for j in cluster.centroid_indices[:max_reps]
            ]

            # 1. Get LLM response
            theme_data = self._get_theme_from_llm(product_name, reps)
            
            if theme_data:
                # 2. Validate quotes against ALL reviews in this cluster
                all_cluster_texts = [r.text for r in cluster.reviews]
                valid_quotes = self.validator.validate(theme_data.get("quotes", []), all_cluster_texts)
                
                # 3. Create Theme object
                themes.append(Theme(
                    name=theme_data.get("name", "Unknown Theme"),
                    description=theme_data.get("description", ""),
                    quotes=valid_quotes,
                    action_ideas=theme_data.get("action_ideas", [])
                ))

        print(f"[*] Total tokens used for summarization: {self.total_tokens_used}")
        return themes

    def _get_theme_from_llm(self, product_name: str, representative_reviews: List[str]) -> Optional[dict]:
        """Calls Groq API with retry-on-429, updates token usage, parses JSON response."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": get_user_prompt(product_name, representative_reviews)},
        ]
        for attempt in range(1, 5):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                usage = response.usage
                if usage:
                    self.total_tokens_used += usage.total_tokens
                return json.loads(response.choices[0].message.content)
            except RateLimitError:
                wait = 10 * attempt
                print(f"[!] Groq 429 — waiting {wait}s before retry (attempt {attempt}/4)...")
                time.sleep(wait)
            except Exception as e:
                print(f"Error calling LLM for cluster: {e}")
                return None
        print("[!] Cluster skipped after 4 failed attempts (rate limit).")
        return None

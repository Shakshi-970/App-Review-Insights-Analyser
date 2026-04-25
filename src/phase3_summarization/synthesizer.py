import json
from typing import List, Optional
from groq import Groq

from src.phase0_foundations.config import settings
from src.phase0_foundations.models import Cluster, Theme
from src.phase3_summarization.prompts import SYSTEM_PROMPT, get_user_prompt
from src.phase3_summarization.quote_validator import QuoteValidator

class Synthesizer:
    """
    Orchestrates the LLM summarization of clusters into themes.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = model_name or settings.DEFAULT_MODEL
        self.validator = QuoteValidator()
        self.total_tokens_used = 0

    def synthesize_clusters(self, product_name: str, clusters: List[Cluster]) -> List[Theme]:
        """
        Processes each cluster and returns a list of validated Themes.
        """
        themes: List[Theme] = []
        self.total_tokens_used = 0

        for cluster in clusters:
            # Check budget before processing next cluster
            if self.total_tokens_used >= settings.TOKEN_BUDGET_PER_RUN:
                print(f"[!] Token budget exceeded ({self.total_tokens_used} tokens). Stopping summarization.")
                break

            # Only summarize if there are enough reviews
            if not cluster.reviews:
                continue

            # Extract representative review texts (centroid indices)
            reps = [cluster.reviews[i].text for i in cluster.centroid_indices]
            
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
        """Calls Groq API, updates token usage, and parses JSON response."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": get_user_prompt(product_name, representative_reviews)}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Track tokens
            usage = response.usage
            if usage:
                self.total_tokens_used += usage.total_tokens

            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            print(f"Error calling LLM for cluster: {e}")
            return None

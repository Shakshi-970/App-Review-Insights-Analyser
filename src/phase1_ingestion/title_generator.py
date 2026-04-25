import json
import time
from groq import Groq, RateLimitError
from src.phase0_foundations.config import settings


class TitleGenerator:
    """
    Generates unique 4-5 word LLM summary titles for reviews.
    On rate-limit errors, halves the batch size and retries automatically.
    """

    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.DEFAULT_MODEL
        self.batch_size = 20
        self.inter_batch_delay = 4  # seconds between batches
        self.min_batch_size = 3
        self.max_retries = 4

    def _build_prompt(self, texts: list[str]) -> str:
        numbered = "\n".join([f"{i+1}. {t[:250]}" for i, t in enumerate(texts)])
        return (
            "For each review below, write a unique 4-5 word title that summarises its main point.\n"
            "Rules:\n"
            "- Do NOT copy exact phrases from the review\n"
            "- Every title must be different from the others\n"
            "- Use neutral, professional language\n\n"
            f"{numbered}\n\n"
            "Reply with ONLY a JSON array of strings, one per review.\n"
            'Example: ["Excessive hidden fees charged", "Smooth stock trading experience"]'
        )

    def _call_llm(self, texts: list[str]) -> list[str]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": self._build_prompt(texts)}],
            temperature=0.4,
            max_tokens=600,
        )
        content = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if "```" in content:
            parts = content.split("```")
            content = parts[1] if len(parts) > 1 else content
            if content.startswith("json"):
                content = content[4:]

        titles = json.loads(content.strip())

        # Pad or truncate to match input length
        while len(titles) < len(texts):
            titles.append("User Review")
        return titles[: len(texts)]

    def _generate_chunk(self, texts: list[str], max_batch: int) -> list[str]:
        """
        Generate titles for `texts` using batches no larger than `max_batch`.
        Recursively halves the batch on RateLimitError.
        """
        if not texts:
            return []

        results: list[str] = []
        i = 0
        while i < len(texts):
            chunk = texts[i : i + max_batch]
            titles = self._call_chunk_with_retry(chunk, max_batch)
            results.extend(titles)
            i += len(chunk)
            if i < len(texts):
                time.sleep(self.inter_batch_delay)

        return results

    def _call_chunk_with_retry(self, chunk: list[str], current_max: int) -> list[str]:
        """Single chunk: retry with backoff; on rate-limit halve the batch recursively."""
        for attempt in range(self.max_retries):
            try:
                return self._call_llm(chunk)

            except RateLimitError:
                new_max = max(self.min_batch_size, current_max // 2)
                wait = 20 * (attempt + 1)
                print(
                    f"    [rate-limit] batch {len(chunk)} -> splitting to max {new_max}, "
                    f"waiting {wait}s (attempt {attempt+1}/{self.max_retries})..."
                )
                time.sleep(wait)

                if new_max < len(chunk):
                    # Split this chunk into smaller pieces and recurse
                    return self._generate_chunk(chunk, new_max)
                # Already at minimum batch size — just wait and retry the same chunk

            except Exception as e:
                err_str = str(e)
                # Permanent errors: don't retry, fail fast
                if "model_decommissioned" in err_str or "invalid_request_error" in err_str:
                    raise RuntimeError(
                        f"Permanent API error (check model name in config): {err_str}"
                    ) from e
                if attempt < self.max_retries - 1:
                    wait = (attempt + 1) * 6
                    print(f"    [error] retry {attempt+1}/{self.max_retries} in {wait}s: {e}")
                    time.sleep(wait)
                else:
                    print(f"    [failed] giving up on {len(chunk)} reviews: {e}")
                    return ["User Review"] * len(chunk)

        return ["User Review"] * len(chunk)

    def generate_all_titles(self, reviews_texts: list[str]) -> list[str]:
        total = len(reviews_texts)
        n_batches = (total + self.batch_size - 1) // self.batch_size
        print(f"  Generating titles: {total} reviews in ~{n_batches} batches of max {self.batch_size}...")
        return self._generate_chunk(reviews_texts, self.batch_size)

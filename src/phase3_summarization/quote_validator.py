from typing import List
import difflib

class QuoteValidator:
    """
    Verifies that LLM-returned quotes are actually present in the original review corpus.
    """

    def validate(self, suggested_quotes: List[str], original_corpus: List[str]) -> List[str]:
        """
        Returns only the quotes that are found as substrings in the corpus.
        Optional: Handle minor punctuation/whitespace differences.
        """
        valid_quotes = []
        # Normalize corpus for easier matching
        normalized_corpus = [self._normalize(r) for r in original_corpus]

        for quote in suggested_quotes:
            normalized_quote = self._normalize(quote)
            if not normalized_quote:
                continue

            # Check for exact substring match in any review
            is_valid = False
            for review in normalized_corpus:
                if normalized_quote in review:
                    is_valid = True
                    # Return the original casing/punctuation from the corpus if possible, 
                    # but for simplicity we'll just keep the LLM one if it's "close enough"
                    # or find the actual segment.
                    valid_quotes.append(quote)
                    break
            
            if not is_valid:
                # Optional: try fuzzy match or partial match if needed
                pass
        
        return valid_quotes

    def _normalize(self, text: str) -> str:
        """Simple normalization: lowercase and strip extra whitespace."""
        return " ".join(text.lower().split())

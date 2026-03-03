import math
import requests
from dataclasses import dataclass
from typing import Optional

@dataclass
class LitSenseObject:
    """Dataclass for a single result from the LitSense API."""
    text: str
    score: float
    annotations: list[str]
    pmid: int
    pmcid: str
    section: str


class LitSense_API:
    """Python wrapper for the LitSense API."""
    def __init__(
        self,
        base_url="https://www.ncbi.nlm.nih.gov/research/litsense2-api/api/",
    ):
        self.base_url = base_url


    def retrieve(
        self,
        query_str: str,
        rerank: bool = True,
        limit: int = 20,
        min_score: Optional[float] = None,
        mode: str = 'passages'
    ) -> list[LitSenseObject]:
        """Retrieve results from the NCBI LitSense2 API for passages or sentences.

        This method sends a GET request to the LitSense2 API and returns a list
        of `LitSenseObject` instances parsed from the JSON response. Optional
        client-side filtering by `min_score` can be applied after the API call.

        Args:
            query_str: The search query string. Must be a non-empty string.
            rerank: Whether to let the service re-rank results. Defaults to True.
            limit: Maximum number of results to return. Must be >= 1. Defaults to 10.
            min_score: Optional minimum score threshold in [0.0, 1.0]. If provided,
                results with scores below this value are filtered out.
            mode: Which endpoint to query: 'passages' (default) or 'sentences'.

        Returns:
            A list of `LitSenseObject` items representing the API results.

        Raises:
            TypeError: If any argument has an invalid type.
            ValueError: If any argument fails validation or the API response is malformed.
            requests.HTTPError: If the HTTP response status indicates an error.
        """

        # Input validation layer 
        if not isinstance(query_str, str):
            raise TypeError("query_str must be a string")
        if not query_str.strip():
            raise ValueError("query_str cannot be empty")

        if not isinstance(rerank, bool):
            raise TypeError("rerank must be a bool")

        if not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        if limit < 1:
            raise ValueError("limit must be >= 1")

        if min_score is not None:
            if not isinstance(min_score, (int, float)):
                raise TypeError("min_score must be a float")
            if math.isnan(float(min_score)) or math.isinf(float(min_score)):
                raise ValueError("min_score must be a finite number")
            if not (0.0 <= float(min_score) <= 1.0):
                raise ValueError("min_score must be between 0.0 and 1.0 inclusive")

        if mode not in {"passages", "sentences"}:
            raise ValueError("mode must be either 'passages' or 'sentences'")
        if not isinstance(self.base_url, str) or not self.base_url:
            raise ValueError("base_url must be a non-empty string")
        if not self.base_url.endswith('/'):
            raise ValueError("base_url must end with '/'")

        url = self.base_url + 'sentences/'
        if mode == 'passages':
            url = self.base_url + 'passages/'
        
        # Main function
        params = {"query": query_str, "rerank": rerank, "limit": limit}
        response = requests.get(url, params=params)
        response.raise_for_status()

        results = response.json()
        if not isinstance(results, list):
            raise ValueError("Unexpected API response format: expected a list")
        try:
            parsed_results = [LitSenseObject(**result) for result in results]
        except Exception as exc:
            raise ValueError(f"Failed to parse API response items: {exc}") from exc

        if min_score:
            parsed_results = [
                result
                for result in parsed_results
                if result.score >= min_score
            ]

        return parsed_results
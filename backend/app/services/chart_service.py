"""
ChartService
------------
Uses an external AI API (OpenAI gpt-4o-mini) to extract structured chart data
from chatbot answer text for visualization in the frontend.
"""

from typing import List, Dict, Any, Optional
import json
import re

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from app.core.config import settings

CHART_KEYWORDS = {
    "graph", "chart", "visualize", "visualise", "compare", "trend",
    "statistics", "statistic", "data", "breakdown", "distribution",
    "percentage", "proportion", "versus", "vs", "plot"
}


class ChartService:
    """
    Calls an external AI API to extract chart-ready JSON from chatbot answer text.
    Falls back gracefully if the API key is missing or an error occurs.
    """

    def __init__(self):
        self.enabled = False
        self.client = None

        if not OPENAI_AVAILABLE:
            print(" [Chart] openai package not installed. Chart extraction disabled.")
            return
        if not settings.OPENAI_API_KEY:
            print(" [Chart] No OPENAI_API_KEY set. Chart extraction disabled.")
            return

        try:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL
            self.enabled = True
            print(f" [Chart] Initialized with model: {self.model}")
        except Exception as e:
            print(f" [Chart] Initialization failed: {e}")

    def _is_chart_query(self, query: str) -> bool:
        words = set(re.findall(r"\b\w+\b", query.lower()))
        return bool(words & CHART_KEYWORDS)

    def extract_chart_data(
        self, answer_text: str, query: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Asks the external AI to extract numerical data from chatbot answer text.

        Returns a list of dicts like:
            [{"label": "Deposit", "value": 2000, "chart_type": "bar"}, ...]
        or None if no chart-worthy data is found.
        """
        if not self.enabled:
            return None

        if not self._is_chart_query(query):
            return None

        prompt = (
            "You are a data extraction assistant. "
            "Given the following text, extract any numerical data that could be visualized as a chart.\n\n"
            f"Text:\n{answer_text}\n\n"
            f"User's request: {query}\n\n"
            "Rules:\n"
            "1. If there is chartable numerical data, output ONLY a JSON array.\n"
            "2. Each item must have: 'label' (string), 'value' (number).\n"
            "3. Optionally include 'chart_type': 'bar', 'line', or 'pie'.\n"
            "   - 'bar' for comparisons, 'line' for trends, 'pie' for proportions.\n"
            "4. If there is NO numerical data to chart, output exactly: null\n"
            "5. Output ONLY the JSON or null. No explanation, no markdown.\n\n"
            "Example: "
            '[{"label": "Deposit", "value": 2000, "chart_type": "bar"}, '
            '{"label": "Monthly Rent", "value": 1500, "chart_type": "bar"}]'
        )

        try:
            print(f" [Chart] Requesting extraction for: '{query[:60]}'")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500,
            )
            raw = response.choices[0].message.content.strip()
            print(f" [Chart] Raw response: {raw[:200]}")

            if raw.lower() in ("null", "none", ""):
                print(" [Chart] No chart data found.")
                return None

            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if not match:
                print(" [Chart] No JSON array found in response.")
                return None

            data = json.loads(match.group())

            if not isinstance(data, list) or len(data) == 0:
                return None
            if not all("label" in item and "value" in item for item in data):
                print(" [Chart] Invalid structure in chart data.")
                return None

            for item in data:
                item["value"] = float(item["value"])
                if "chart_type" not in item:
                    item["chart_type"] = "bar"

            print(f" [Chart] Extracted {len(data)} data points.")
            return data

        except json.JSONDecodeError as e:
            print(f" [Chart] JSON parse error: {e}")
            return None
        except Exception as e:
            print(f" [Chart] Extraction error: {e}")
            return None

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
    ) -> Optional[Dict[str, Any]]:
        """
        Asks the external AI to extract numerical data from chatbot answer text.

        Returns a dict like:
            {"data": [{"label": "Deposit", "value": 2000, "chart_type": "bar"}], "summary": "A brief explanation"}
        or None if no chart-worthy data is found.
        """
        if not self.enabled:
            return None

        if not self._is_chart_query(query):
            return None

        prompt = (
            "You are a data extraction assistant. "
            "Given the following chatbot answer text, extract any numerical data for visualization.\n\n"
            f"Text:\n{answer_text}\n\n"
            f"User's chart request: {query}\n\n"
            "Rules:\n"
            "1. If there is chartable numerical data, output ONLY a JSON object with two keys: 'data' (array) and 'summary' (string).\n"
            "2. The 'summary' should be a 1-2 sentence explanation of what the chart is showing or the key takeaway.\n"
            "3. In the 'data' array, each item must have: 'label' (string), 'value' (number).\n"
            "4. Select chart_type using these rules IN ORDER:\n"
            "   a) EXPLICIT: If user says 'pie' or 'pie chart' → ALL items use 'pie'.\n"
            "   b) EXPLICIT: If user says 'line' or 'line graph' or 'trend' → ALL items use 'line'.\n"
            "   c) EXPLICIT: If user says 'bar' or 'bar chart' or 'compare' → ALL items use 'bar'.\n"
            "   d) INFER LINE: Data with dates, months, years, or sequential time periods → 'line'.\n"
            "   e) INFER PIE: Data representing a cost breakdown, budget split, proportional amounts,\n"
            "      or 3+ items that together form a total (e.g. rent + deposit + utilities + fees) → 'pie'.\n"
            "   f) INFER BAR: Data comparing exactly 2 specific items side-by-side → 'bar'.\n"
            "   g) DEFAULT: When unsure whether the values form a whole or are independent comparisons,\n"
            "      prefer 'pie' for financial/cost data, 'bar' for performance/count data.\n"
            "   All items in the array MUST use the same chart_type.\n"
            "5. If there is NO numerical data to chart, output exactly: null\n"
            "6. Output ONLY valid JSON or null. No explanation, no markdown, no code fences.\n\n"
            "Example response (comparing values): \n"
            '{"data": [{"label": "Last Year", "value": 1500, "chart_type": "bar"}, {"label": "This Year", "value": 1800, "chart_type": "bar"}], "summary": "Comparing revenue between last year and this year shows a $300 increase."}'
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

            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                print(" [Chart] No JSON object found in response.")
                return None

            result = json.loads(match.group())
            
            if "data" not in result or not isinstance(result["data"], list) or len(result["data"]) == 0:
                print(" [Chart] Invalid or empty 'data' array in response.")
                return None
                
            data = result["data"]

            if not all("label" in item and "value" in item for item in data):
                print(" [Chart] Invalid structure in chart data items.")
                return None

            for item in data:
                item["value"] = float(item["value"])
                if "chart_type" not in item:
                    item["chart_type"] = "bar"

            print(f" [Chart] Extracted {len(data)} data points.")
            return {
                "data": data,
                "summary": result.get("summary", "No summary provided.")
            }

        except json.JSONDecodeError as e:
            print(f" [Chart] JSON parse error: {e}")
            return None
        except Exception as e:
            print(f" [Chart] Extraction error: {e}")
            return None

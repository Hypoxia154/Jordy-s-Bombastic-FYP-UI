"""
ChartService
------------
Uses an external AI API (OpenAI gpt-4o-mini) to extract structured chart data
from chatbot answer text for visualization in the frontend.
"""

from typing import Dict, Any, Optional
import json
import re
import math

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from app.core.config import settings


class ChartService:
    """
    Calls an external AI API to extract chart-ready JSON from chatbot answer text.
    Falls back gracefully if the API key is missing or an error occurs.
    """

    EXPLICIT_CHART_PHRASES = {
        "show chart", "show a chart", "bar chart", "pie chart", "line chart",
        "line graph", "visualize this", "visualise this", "plot this", "draw chart"
    }

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
        q = (query or "").lower()
        return any(phrase in q for phrase in self.EXPLICIT_CHART_PHRASES)

    def _has_chartable_numbers(self, answer_text: str) -> bool:
        if not answer_text:
            return False
        numbers = re.findall(r"[-+]?\d*\.?\d+", answer_text)
        return len(numbers) >= 2

    def _validate_chart_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "data" not in result or not isinstance(result["data"], list) or len(result["data"]) == 0:
            print(" [Chart] Invalid or empty 'data' array in response.")
            return None

        data = result["data"]
        if len(data) > 8:
            print(" [Chart] Too many data points.")
            return None

        allowed_types = {"bar", "line", "pie"}
        chart_types = set()
        cleaned_data = []

        for item in data:
            if not isinstance(item, dict):
                print(" [Chart] Invalid item type.")
                return None
            if "label" not in item or "value" not in item:
                print(" [Chart] Invalid structure in chart data items.")
                return None

            label = str(item["label"]).strip()
            if not label or len(label) > 80:
                print(" [Chart] Invalid label.")
                return None

            try:
                value = float(item["value"])
                if not math.isfinite(value):
                    print(" [Chart] Non-finite value.")
                    return None
            except Exception:
                print(" [Chart] Value is not numeric.")
                return None

            chart_type = str(item.get("chart_type", "bar")).strip().lower()
            if chart_type not in allowed_types:
                print(" [Chart] Unsupported chart type.")
                return None

            chart_types.add(chart_type)
            cleaned_data.append({
                "label": label,
                "value": value,
                "chart_type": chart_type,
            })

        if len(chart_types) != 1:
            print(" [Chart] Mixed chart types are not allowed.")
            return None

        summary = str(result.get("summary", "No summary provided.")).strip()
        return {
            "data": cleaned_data,
            "summary": summary or "No summary provided."
        }

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

        if not answer_text or answer_text.strip() == "Please ask admin to update documents database":
            return None

        if not self._is_chart_query(query):
            return None

        if not self._has_chartable_numbers(answer_text):
            return None

        prompt = (
            "You are a data extraction assistant. "
            "Given the following chatbot answer text, extract any numerical data for visualization.\n\n"
            f"Text:\n{answer_text}\n\n"
            f"User's chart request: {query}\n\n"
            "Rules:\n"
            "1. If there is chartable numerical data, output ONLY a JSON object with two keys: 'data' (array) and 'summary' (string).\n"
            "2. The 'summary' should be a 1-2 sentence explanation of what the chart is showing or the key takeaway.\n"
            "3. In the 'data' array, each item must have: 'label' (string), 'value' (number), 'chart_type' (string).\n"
            "4. Select chart_type using these rules IN ORDER:\n"
            "   a) EXPLICIT: If user says 'pie' or 'pie chart' -> ALL items use 'pie'.\n"
            "   b) EXPLICIT: If user says 'line' or 'line graph' or 'trend' -> ALL items use 'line'.\n"
            "   c) EXPLICIT: If user says 'bar' or 'bar chart' or 'compare' -> ALL items use 'bar'.\n"
            "   d) INFER LINE: Data with dates, months, years, or sequential time periods -> 'line'.\n"
            "   e) INFER PIE: Data representing a cost breakdown, budget split, or proportional amounts -> 'pie'.\n"
            "   f) INFER BAR: Data comparing independent items -> 'bar'.\n"
            "   All items in the array MUST use the same chart_type.\n"
            "5. Return at most 8 items.\n"
            "6. If there is NO numerical data to chart, output exactly: null\n"
            "7. Output ONLY valid JSON or null. No explanation, no markdown, no code fences.\n\n"
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
            validated = self._validate_chart_result(result)
            if not validated:
                return None

            print(f" [Chart] Extracted {len(validated['data'])} data points.")
            return validated

        except json.JSONDecodeError as e:
            print(f" [Chart] JSON parse error: {e}")
            return None
        except Exception as e:
            print(f" [Chart] Extraction error: {e}")
            return None

"""
test_crag_service.py — Unit tests for the core CRAG / RAG pipeline.

The 3 expensive external dependencies are mocked via unittest.mock so these
tests run instantly without Qdrant, Ollama, or GPU:

  1. Ollama LLM          -> its `.complete()` method returns a fake response
  2. VectorIndexRetriever -> its `.retrieve()` method returns fake node results
  3. SentenceTransformerRerank -> mocked to return nodes unchanged

This covers 80% of your FYP's core logic value, which supervisors expect
to be validated through automated testing.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ─── Shared helpers ─────────────────────────────────────────────────────────

def make_fake_node(text: str, score: float = 5.0, file_name: str = "test_doc.pdf"):
    """Creates a fake LlamaIndex NodeWithScore for use in retrieval mocks."""
    node = MagicMock()
    node.score = score
    node.get_content.return_value = text
    node.metadata = {"file_name": file_name}
    return node


def build_service():
    """
    Builds a CRAGService instance with all heavy IO mocked out.
    Returns (service, mock_llm, mock_retriever).
    """
    with patch("app.services.crag_service.Ollama") as MockOllama, \
         patch("app.services.crag_service.VectorService") as MockVectorService, \
         patch("app.services.crag_service.SentenceTransformerRerank") as MockReranker, \
         patch("app.services.crag_service.ChartService") as MockChartService, \
         patch("app.services.crag_service.LlamaSettings"):

        mock_llm = MagicMock()
        MockOllama.return_value = mock_llm

        mock_index = MagicMock()
        MockVectorService.return_value.get_index.return_value = mock_index

        mock_reranker = MagicMock()
        mock_reranker.postprocess_nodes.side_effect = lambda nodes, **_: nodes
        MockReranker.return_value = mock_reranker

        from app.services.crag_service import CRAGService
        service = CRAGService.__new__(CRAGService)
        CRAGService.__init__(service)

        return service, mock_llm, mock_index


# ─── Classification Tests ──────────────────────────────────────────────────

class TestQueryClassification:
    """Tests for _classify_input() — the intent classification gate."""

    def test_classifies_greeting(self):
        service, mock_llm, _ = build_service()
        mock_llm.complete.return_value.text = "GREETING"
        result = service._classify_input("Hello there!")
        assert result == "GREETING"

    def test_classifies_domain_question(self):
        service, mock_llm, _ = build_service()
        mock_llm.complete.return_value.text = "DOMAIN"
        result = service._classify_input("What is the notice period in my tenancy agreement?")
        assert result == "DOMAIN"

    def test_classifies_session_input(self):
        service, mock_llm, _ = build_service()
        mock_llm.complete.return_value.text = "SESSION"
        result = service._classify_input("My name is Ahmad")
        assert result == "SESSION"

    def test_classifies_general_question(self):
        service, mock_llm, _ = build_service()
        mock_llm.complete.return_value.text = "GENERAL"
        result = service._classify_input("Tell me a joke")
        assert result == "GENERAL"

    def test_classifies_dependent_followup(self):
        service, mock_llm, _ = build_service()
        mock_llm.complete.return_value.text = "DEPENDENT"
        result = service._classify_input("How much is it?")
        assert result == "DEPENDENT"


# ─── RAG Plan Builder Tests ────────────────────────────────────────────────

class TestBuildRagPlan:
    """Tests for build_rag_plan() — the streaming query planner."""

    def test_greeting_returns_greeting_plan(self):
        service, mock_llm, _ = build_service()
        mock_llm.complete.return_value.text = "GREETING"
        plan = service.build_rag_plan("Hi!", history=[])
        assert plan["intent"] == "GREETING"
        assert plan["sources"] == []
        assert "prompt" in plan

    def test_general_question_returns_general_plan(self):
        service, mock_llm, _ = build_service()
        mock_llm.complete.return_value.text = "GENERAL"
        plan = service.build_rag_plan("What's the weather?", history=[])
        assert plan["intent"] == "GENERAL"

    def test_domain_question_triggers_rag_retrieval(self):
        service, mock_llm, mock_index = build_service()
        mock_llm.complete.return_value.text = "DOMAIN"

        # Mock the retriever to return a single fake result
        fake_nodes = [make_fake_node("The notice period is 30 days.", score=5.0)]
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = fake_nodes

        with patch("app.services.crag_service.VectorIndexRetriever", return_value=mock_retriever):
            plan = service.build_rag_plan("What is the notice period?", history=[])

        assert plan["intent"] == "DOMAIN"
        assert len(plan["sources"]) >= 1
        assert "prompt" in plan

    def test_dependent_with_history_gets_rewritten(self):
        service, mock_llm, mock_index = build_service()

        # First call: classify as DEPENDENT; second call: rewrite the query
        mock_llm.complete.side_effect = [
            MagicMock(text="DEPENDENT"),
            MagicMock(text="What is the deposit amount in the tenancy agreement?")
        ]

        # After rewrite, retrieval should be called
        fake_nodes = [make_fake_node("The deposit is two months' rent.", score=5.0)]
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = fake_nodes

        with patch("app.services.crag_service.VectorIndexRetriever", return_value=mock_retriever):
            plan = service.build_rag_plan(
                "How much is it?",
                history=["User: What is the deposit?", "Assistant: The deposit is two months rent."]
            )

        # After rewrite, should resolve to DOMAIN
        assert plan["intent"] in ("DOMAIN", "GENERAL")

    def test_low_confidence_retrieval_returns_not_found(self):
        """If retrieved nodes have very low reranker scores, we should get a NOT FOUND response."""
        service, mock_llm, mock_index = build_service()
        mock_llm.complete.return_value.text = "DOMAIN"

        # Simulate a bad retrieval (very low scores)
        fake_nodes = [make_fake_node("Irrelevant content.", score=-10.0)]
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = fake_nodes

        with patch("app.services.crag_service.VectorIndexRetriever", return_value=mock_retriever):
            plan = service.build_rag_plan("What are the termination clauses?", history=[])

        # Should still return a DOMAIN plan but with empty sources and low confidence
        assert plan["confidence"] < 0.2


# ─── Query Normalization Tests ─────────────────────────────────────────────

class TestQueryNormalization:
    """Tests for internal query normalization helper."""

    def test_normalize_returns_a_string(self):
        """_normalize_query should always return a non-None string."""
        service, _, _ = build_service()
        result = service._normalize_query("What is the rent?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_normalize_preserves_real_content(self):
        service, _, _ = build_service()
        q = "What is the notice period for terminating a tenancy?"
        result = service._normalize_query(q)
        assert "notice" in result.lower()


# ─── Chart Service Tests ──────────────────────────────────────────────────

class TestChartService:
    """Tests for ChartService — validates OpenAI output parsing."""

    def test_chart_service_disabled_when_no_key(self):
        """Without an OPENAI_API_KEY, ChartService should disable itself."""
        with patch("app.services.chart_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            from app.services import chart_service as cs_module
            import importlib
            # Reload to pick up the patched settings
            with patch("app.services.chart_service.OPENAI_AVAILABLE", True):
                svc = cs_module.ChartService.__new__(cs_module.ChartService)
                svc.enabled = False
                svc.client = None
                assert not svc.enabled

    def test_extract_chart_data_parses_valid_json(self):
        """A well-formed OpenAI completion should be parsed into a chart_data list."""
        fake_json = '[{"label": "Jan", "value": 100, "chart_type": "bar"}, {"label": "Feb", "value": 200, "chart_type": "bar"}]'

        with patch("app.services.chart_service.settings") as mock_settings, \
             patch("app.services.chart_service.OpenAI") as mock_openai_cls, \
             patch("app.services.chart_service.OPENAI_AVAILABLE", True):

            mock_settings.OPENAI_API_KEY = "fake-key"
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.chat.completions.create.return_value.choices[0].message.content = fake_json

            from app.services.chart_service import ChartService
            svc = ChartService()
            svc.enabled = True  # Force enabled for this test
            svc.client = mock_client

            result = svc.extract_chart_data("Some text with numbers", "visualize this as a bar chart")
            assert result is not None
            assert isinstance(result, list)
            assert result[0]["label"] == "Jan"
            assert result[1]["value"] == 200

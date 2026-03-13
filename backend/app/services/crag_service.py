from typing import List, Dict, Any, Optional
import json
import re
import os
import tempfile
import math
from collections import Counter
from datetime import datetime

from llama_index.llms.ollama import Ollama
from llama_index.core import Settings as LlamaSettings, get_response_synthesizer, PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank

from app.core.config import settings
from app.services.vector_store import VectorService
from app.services.chart_service import ChartService
from app.db.sqlite import db


class CRAGService:
    ADMIN_UPDATE_MESSAGE = "No relevant infomation found!! Please contact admin to update documents database."
    KL_SCOPE_MESSAGE = "This chatbot is limited to Kuala Lumpur real estate scope for this FYP."

    KL_LOCATION_TERMS = {
        "kuala lumpur", "kl", "setapak", "wangsa maju", "sentul", "kepong", "segambut",
        "mont kiara", "sri hartamas", "desa petaling", "kuchai lama", "old klang road",
        "okr", "oug", "bangsar", "bangsar south", "brickfields", "bukit jalil",
        "sri petaling", "cheras", "ampang hilir", "jalan ipoh", "klcc", "bukit bintang",
        "pudu", "chan sow lin", "titiwangsa", "sungai besi", "pandan indah",
        "pandan jaya", "damansara heights", "jalan tun razak", "jalan ampang",
        "kampung baru", "kg baru", "taman desa", "desa pandan", "maluri", "cochrane",
        "publika", "dutamas", "jinjang", "kepong baru", "bandar menjalara",
        "jalan kuching", "sentul west", "sentul east", "bandar tun razak",
        "bandar sri permaisuri", "alam damai", "tasik permaisuri", "setiawangsa",
        "jelatek", "pwtc", "putra world trade centre", "kl sentral", "federal hill",
        "happy garden"
    }

    NON_KL_LOCATION_TERMS = {
        "johor", "johor bahru", "jb", "penang", "georgetown", "selangor", "shah alam",
        "petaling jaya", "pj", "puchong", "cyberjaya", "putrajaya", "kajang", "klang",
        "seremban", "melaka", "malacca", "ipoh", "perak", "kedah", "perlis",
        "terengganu", "kelantan", "pahang", "sabah", "sarawak", "labuan",
        "negeri sembilan", "kota kinabalu", "kk", "kuching", "miri", "nilai",
        "rawang", "ampang jaya", "selayang", "gombak", "sunway", "bandar sunway",
        "damansara", "ara damansara", "kota damansara", "semenyih", "subang jaya"
    }

    DOMAIN_TERMS = {
        "property", "real estate", "tenancy", "tenant", "landlord", "rent", "rental",
        "lease", "agreement", "contract", "deposit", "security deposit", "earnest deposit",
        "booking fee", "termination", "eviction", "notice", "premises", "maintenance",
        "utilities", "inspection", "renewal", "sublet", "sublease", "occupancy",
        "arrears", "late fee", "rights", "obligation", "clause", "condo", "condominium",
        "apartment", "house", "landed", "commercial", "office", "shoplot", "sale",
        "purchase", "spa", "mot", "title", "strata title", "individual title",
        "valuation", "market value", "loan", "mortgage", "financing", "agent fee",
        "commission", "quit rent", "cukai tanah", "assessment", "cukai pintu",
        "developer", "subsale", "ownership", "transfer"
    }

    STATIC_GREETINGS = {
        "hello": "Hello! I’m your Kuala Lumpur Real Estate Assistant.",
        "hi": "Hello! I’m your Kuala Lumpur Real Estate Assistant.",
        "hey": "Hello! I’m your Kuala Lumpur Real Estate Assistant.",
        "good morning": "Hello! I’m your Kuala Lumpur Real Estate Assistant.",
        "good afternoon": "Hello! I’m your Kuala Lumpur Real Estate Assistant.",
        "good evening": "Hello! I’m your Kuala Lumpur Real Estate Assistant.",
        "thanks": "You're welcome.",
        "thank you": "You're welcome.",
        "bye": "Goodbye.",
    }

    def __init__(self):
        print(f" [CRAG] Initializing with Model: {settings.LLM_MODEL}...")

        self.llm = Ollama(
            model=settings.LLM_MODEL,
            request_timeout=300.0,
            temperature=0.1,
            additional_kwargs={
                "num_ctx": 4096,
                "num_predict": 1000,
                "stop": [
                    "<|end|>",
                    "<|user|>",
                    "<|assistant|>",
                    "---------------------",
                ],
            },
        )
        LlamaSettings.llm = self.llm

        self.vector_service = VectorService()
        self.index = self.vector_service.get_index()
        self.reranker = SentenceTransformerRerank(model=settings.RERANKER_MODEL, top_n=5)
        self.chart_service = ChartService()

        self.classify_prompt = PromptTemplate(
            "Classify the User Input into exactly one category:\n"
            "1. GREETING: (Hello, Hi, Thanks, Bye)\n"
            "2. SESSION: (User name, preferences)\n"
            "3. GENERAL: (Greeting, chatbot usage, scope questions only)\n"
            "4. DOMAIN: (Kuala Lumpur real estate, property, tenancy, sale, purchase, rent, title, valuation, agent fee, financing, developer, tax terms)\n"
            "5. DEPENDENT: (Ambiguous follow-ups)\n\n"
            "Examples:\n"
            "User: 'Hi there' -> GREETING\n"
            "User: 'My name is John' -> SESSION\n"
            "User: 'What can you help with?' -> GENERAL\n"
            "User: 'What is the booking fee?' -> DOMAIN\n"
            "User: 'How much is it?' -> DEPENDENT\n\n"
            "User Input: {query_str}\n"
            "Answer ONLY with the Category Name."
        )

        self.session_prompt = PromptTemplate(
            "User Input: {query_str}\n"
            "Extract the name they want to be called. If none, output NONE.\n"
            "Answer with ONLY the name or NONE.\n"
            "Name:"
        )

        self.multiquery_prompt = PromptTemplate(
            "Rewrite the user's follow-up question into a standalone search query for retrieval.\n"
            "Use conversation context. Keep the wording grounded and factual.\n"
            "Context:\n{history_str}\n\n"
            "Follow-up:\n{query_str}\n\n"
            "Output ONLY the rewritten standalone question."
        )

        self.qa_prompt_tmpl = (
            "<|user|>\n"
            "ROLE: You are a document-grounded assistant for Kuala Lumpur real estate matters only.\n"
            "TASK: Answer the user's question using ONLY the Context.\n\n"
            "HARD RULES:\n"
            "1) Use ONLY facts found in Context. No outside knowledge.\n"
            f"2) If Context does not contain exact or clearly relevant information, reply exactly: \"{self.ADMIN_UPDATE_MESSAGE}\"\n"
            "3) Do NOT infer, guess, generalize, or add external explanations.\n"
            "4) If topic keywords are missing from Context, reply exactly with the fallback message.\n"
            "5) Ignore irrelevant text in Context.\n"
            "6) Do NOT end with a question.\n"
            "7) Keep the answer concise but useful.\n"
            "8) Use 4-10 bullet points when the answer is supported.\n"
            "9) Avoid repeating the same point in different words.\n\n"
            "ANSWER FORMAT:\n"
            f"- Give 4-10 direct bullet points only when supported.\n- Otherwise output exactly: {self.ADMIN_UPDATE_MESSAGE}\n\n"
            "STYLE:\n"
            "- Around 200-500 words when evidence clearly supports it.\n"
            "- Bullets only when supported.\n\n"
            "---------------------\n"
            "Context:\n"
            "{context_str}\n"
            "---------------------\n"
            "Question: {query_str}\n"
            "<|end|>\n"
            "<|assistant|>\n"
        )
        self.qa_prompt = PromptTemplate(self.qa_prompt_tmpl)

    # ---------------------
    # Public API
    # ---------------------
    def generate_response(
        self,
        query: str,
        history: Optional[List[str]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        history = history or []
        user_context = user_context or {}

        normalized_query = self._normalize_query(query)
        category = self._classify_input(normalized_query)

        if category == "GENERAL" and self._looks_domain_related(normalized_query):
            category = "DOMAIN"

        result_template = {
            "answer": "",
            "sources": [],
            "evidence": [],
            "intent": category,
            "session_updates": {},
            "chart_data": None,
            "confidence": 1.0,
            "bleu_score": 0.0,
        }

        if self._is_explicitly_non_kl_location(normalized_query):
            result_template["answer"] = self.KL_SCOPE_MESSAGE
            result_template["intent"] = "GENERAL"
            result_template["confidence"] = 1.0
            return result_template

        if category == "GREETING":
            result_template["answer"] = self._static_greeting_reply(normalized_query)
            result_template["confidence"] = 0.95
            return result_template

        if category == "SESSION":
            result_template["answer"] = self._handle_session(normalized_query, result_template)
            result_template["confidence"] = 0.85
            return result_template

        if category == "GENERAL":
            result_template["answer"] = self._safe_general_reply(normalized_query)
            result_template["confidence"] = 0.9 if result_template["answer"] != self.ADMIN_UPDATE_MESSAGE else 0.0
            return result_template

        if category == "DEPENDENT":
            search_query = self._rewrite_dependent_query(normalized_query, history)
            if search_query == self.ADMIN_UPDATE_MESSAGE:
                result_template["answer"] = self.ADMIN_UPDATE_MESSAGE
                result_template["confidence"] = 0.0
                return result_template
        else:
            search_query = normalized_query

        if not self._looks_domain_related(search_query) and not self._is_kl_related_location(search_query):
            result_template["answer"] = self.ADMIN_UPDATE_MESSAGE
            result_template["confidence"] = 0.0
            return result_template

        rag_result = self._run_rag_pipeline(search_query)
        final_answer = self._enforce_safe_output(rag_result.get("answer", ""))

        result_template["answer"] = final_answer
        result_template["sources"] = rag_result.get("sources", []) if final_answer != self.ADMIN_UPDATE_MESSAGE else []
        result_template["evidence"] = rag_result.get("evidence", []) if final_answer != self.ADMIN_UPDATE_MESSAGE else []
        result_template["confidence"] = rag_result.get("confidence_score", 0.0)
        result_template["bleu_score"] = rag_result.get("bleu_score", 0.0)

        if final_answer not in {self.ADMIN_UPDATE_MESSAGE, self.KL_SCOPE_MESSAGE}:
            try:
                result_template["chart_data"] = self.chart_service.extract_chart_data(final_answer, normalized_query)
            except Exception:
                result_template["chart_data"] = None

        return result_template

    # ---------------------
    # Streaming plan builder
    # ---------------------
    def build_rag_plan(
        self,
        query: str,
        history: List[str],
        session_state: Optional[dict] = None,
        file_filter: Optional[str] = None,
        accessible_files: Optional[List[str]] = None,
    ) -> dict:
        q = self._normalize_query(query)
        history = history or []
        session_state = session_state or {}
        user_name = (session_state.get("user_name") or "").strip()

        intent = self._classify_input(q)
        if intent == "GENERAL" and self._looks_domain_related(q):
            intent = "DOMAIN"

        print(f" [CRAG] (plan) Intent: {intent} | Query: '{q}'")

        if self._is_explicitly_non_kl_location(q):
            return {
                "intent": "GENERAL",
                "prompt": self._literal_output_prompt(self.KL_SCOPE_MESSAGE),
                "sources": [],
                "confidence": 1.0,
                "chart_data": None,
            }

        if intent == "GREETING":
            return {
                "intent": "GREETING",
                "prompt": self._literal_output_prompt(self._static_greeting_reply(q)),
                "sources": [],
                "confidence": 0.95,
                "chart_data": None,
            }

        if intent == "SESSION":
            return {
                "intent": "SESSION",
                "prompt": self._literal_output_prompt(self._safe_session_acknowledgement(q, user_name=user_name)),
                "sources": [],
                "confidence": 0.85,
                "chart_data": None,
            }

        if intent == "GENERAL":
            return {
                "intent": "GENERAL",
                "prompt": self._literal_output_prompt(self._safe_general_reply(q)),
                "sources": [],
                "confidence": 0.9 if self._safe_general_reply(q) != self.ADMIN_UPDATE_MESSAGE else 0.0,
                "chart_data": None,
            }

        if intent == "DEPENDENT":
            search_query = self._rewrite_dependent_query(q, history)
            if search_query == self.ADMIN_UPDATE_MESSAGE:
                return {
                    "intent": "DOMAIN",
                    "prompt": self._literal_output_prompt(self.ADMIN_UPDATE_MESSAGE),
                    "sources": [],
                    "confidence": 0.0,
                    "chart_data": None,
                }
        else:
            search_query = q

        if not self._looks_domain_related(search_query) and not self._is_kl_related_location(search_query):
            return {
                "intent": "DOMAIN",
                "prompt": self._literal_output_prompt(self.ADMIN_UPDATE_MESSAGE),
                "sources": [],
                "confidence": 0.0,
                "chart_data": None,
            }

        ctx = self._retrieve_context(search_query, file_filter=file_filter, accessible_files=accessible_files)
        if ctx.get("very_low_confidence"):
            return {
                "intent": "DOMAIN",
                "prompt": self._literal_output_prompt(self.ADMIN_UPDATE_MESSAGE),
                "sources": [],
                "confidence": float(ctx.get("confidence", 0.0) or 0.0),
                "chart_data": None,
            }

        context_str = ctx.get("context_str", "")

        if self._needs_party_names(q) and not self._context_mentions_party_names(context_str):
            return {
                "intent": "DOMAIN",
                "prompt": self._literal_output_prompt(self.ADMIN_UPDATE_MESSAGE),
                "sources": [],
                "confidence": float(ctx.get("confidence", 0.0) or 0.0),
                "chart_data": None,
            }

        if not self._has_relevant_coverage(search_query, context_str):
            return {
                "intent": "DOMAIN",
                "prompt": self._literal_output_prompt(self.ADMIN_UPDATE_MESSAGE),
                "sources": [],
                "confidence": float(ctx.get("confidence", 0.0) or 0.0),
                "chart_data": None,
            }

        prompt = self.qa_prompt_tmpl.format(context_str=context_str, query_str=q)
        return {
            "intent": "DOMAIN",
            "prompt": prompt,
            "sources": ctx["sources"],
            "confidence": float(ctx.get("confidence", 0.0) or 0.0),
            "chart_data": None,
        }

    # ---------------------
    # Retrieval / RAG
    # ---------------------
    def _retrieve_context(
        self,
        search_query: str,
        file_filter: Optional[str] = None,
        accessible_files: Optional[List[str]] = None,
    ) -> dict:
        from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
        from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter

        filters_list = []
        if file_filter:
            filters_list.append(ExactMatchFilter(key="file_name", value=file_filter))
        elif accessible_files is not None and len(accessible_files) > 0:
            filters_list.append(MetadataFilter(key="file_name", operator=FilterOperator.IN, value=accessible_files))

        if filters_list:
            filters = MetadataFilters(filters=filters_list)
            retriever = VectorIndexRetriever(index=self.index, similarity_top_k=20, filters=filters)
        else:
            retriever = VectorIndexRetriever(index=self.index, similarity_top_k=20)

        nodes = retriever.retrieve(search_query)
        print(f" [CRAG] Retrieved {len(nodes)} nodes")

        if nodes:
            nodes = self.reranker.postprocess_nodes(nodes, query_str=search_query)

        def sigmoid(x: float) -> float:
            return 1 / (1 + math.exp(-x))

        if not nodes:
            best_score = 0.0
        else:
            best_raw = nodes[0].score if nodes[0].score is not None else -999.0
            best_score = sigmoid(best_raw)

        if not nodes or best_score < 0.30:
            return {
                "context_str": "",
                "sources": [],
                "evidence": [],
                "confidence": best_score,
                "very_low_confidence": True,
            }

        context_parts: List[str] = []
        source_list: List[str] = []
        evidence_list: List[Dict[str, Any]] = []
        bad_prefixes = ("question:", "important:", "tips:", "note:", "sources:", "confidence:")

        for node in nodes:
            text = node.get_content()
            clean_lines = []
            for line in text.splitlines():
                if line.strip().lower().startswith(bad_prefixes):
                    continue
                clean_lines.append(line)

            cleaned_text = "\n".join(clean_lines).strip()
            context_parts.append(cleaned_text[:1100])

            file_name = node.metadata.get("file_name", "Unknown")
            page_label = node.metadata.get("page_label", "N/A")
            raw_node_score = node.score if node.score is not None else -999.0
            norm_score = sigmoid(raw_node_score)

            source_list.append(f"{file_name} (Page {page_label}) - Score: {norm_score:.2f}")
            evidence_list.append({
                "file_name": file_name,
                "page_label": page_label,
                "score": round(norm_score, 4),
                "excerpt": cleaned_text[:600],
            })

        return {
            "context_str": "\n\n---\n\n".join(context_parts),
            "sources": source_list[:3],
            "evidence": evidence_list[:5],
            "confidence": best_score,
            "very_low_confidence": False,
        }

    def _run_rag_pipeline(self, search_query: str) -> dict:
        retriever = VectorIndexRetriever(index=self.index, similarity_top_k=20)
        nodes = retriever.retrieve(search_query)

        if nodes:
            nodes = self.reranker.postprocess_nodes(nodes, query_str=search_query)

        nodes = nodes[:4]

        def sigmoid(x: float) -> float:
            return 1 / (1 + math.exp(-x))

        if not nodes:
            return {
                "answer": self.ADMIN_UPDATE_MESSAGE,
                "sources": [],
                "evidence": [],
                "low_confidence": True,
                "confidence_score": 0.0,
                "bleu_score": 0.0,
            }

        best_raw = nodes[0].score if nodes[0].score is not None else -999.0
        best_score = sigmoid(best_raw)

        if best_score < 0.30:
            return {
                "answer": self.ADMIN_UPDATE_MESSAGE,
                "sources": [],
                "evidence": [],
                "low_confidence": True,
                "confidence_score": best_score,
                "bleu_score": 0.0,
            }

        context_str = self._build_context_from_nodes(nodes)

        if not self._has_relevant_coverage(search_query, context_str):
            return {
                "answer": self.ADMIN_UPDATE_MESSAGE,
                "sources": [],
                "evidence": [],
                "low_confidence": True,
                "confidence_score": best_score,
                "bleu_score": 0.0,
            }

        synthesizer = get_response_synthesizer(
            text_qa_template=self.qa_prompt,
            response_mode="compact",
        )
        response_obj = synthesizer.synthesize(search_query, nodes=nodes)
        answer = self._enforce_safe_output(str(response_obj))

        source_list = []
        evidence = []
        evidence_texts = []

        for node in response_obj.source_nodes:
            file_name = node.metadata.get("file_name", "Unknown")
            page_label = node.metadata.get("page_label", "N/A")
            raw_node_score = node.score if node.score is not None else -999.0
            norm_score = sigmoid(raw_node_score)
            excerpt = node.get_content().strip()[:700]

            source_list.append(f"{file_name} (Page {page_label}) - Score: {norm_score:.2f}")
            evidence_texts.append(excerpt)
            evidence.append({
                "file_name": file_name,
                "page_label": page_label,
                "score": round(norm_score, 4),
                "excerpt": excerpt,
            })

        bleu_score = self._compute_bleu_like(answer, "\n".join(evidence_texts)) if answer != self.ADMIN_UPDATE_MESSAGE else 0.0

        return {
            "answer": answer,
            "sources": source_list[:3],
            "evidence": evidence[:5],
            "low_confidence": best_score < 0.5,
            "confidence_score": best_score,
            "bleu_score": bleu_score,
        }

    # ---------------------
    # Helpers
    # ---------------------
    def _normalize_query(self, query: str) -> str:
        q = (query or "").lower()
        q = q.replace("should included", "should be included")
        q = q.replace("what include", "what is included")
        q = q.replace("where is kfc is", "where is")
        return q.strip()

    def _looks_domain_related(self, query: str) -> bool:
        q = (query or "").lower()
        return self._contains_any_term(q, self.DOMAIN_TERMS)

    def _classify_input(self, query: str) -> str:
        q = (query or "").lower().strip()
        simple = q.strip("!.? ")

        greetings = {
            "hello", "hi", "hey", "thanks", "thank you", "bye",
            "good morning", "good afternoon", "good evening"
        }
        if simple in greetings:
            return "GREETING"

        session_patterns = ["my name is", "call me", "i am ", "i'm "]
        if any(p in q for p in session_patterns):
            return "SESSION"

        if self._is_scope_help_query(q):
            return "GENERAL"

        non_domain_loc_only = ["where is", "location of", "how to go to", "kfc", "mcd", "restaurant", "food", "mall"]
        if any(p in q for p in non_domain_loc_only) and not self._looks_domain_related(q):
            return "GENERAL"

        if self._looks_domain_related(q):
            return "DOMAIN"

        short_followups = {"what about", "how about", "and ", "then ", "give more detail", "elaborate", "explain more"}
        if len(q.split()) <= 5 or any(q.startswith(p) for p in short_followups):
            return "DEPENDENT"

        try:
            prompt = self.classify_prompt.format(query_str=query)
            response = self.llm.complete(prompt).text.strip().upper()
            if "GREETING" in response:
                return "GREETING"
            if "SESSION" in response:
                return "SESSION"
            if "GENERAL" in response:
                return "GENERAL"
            if "DEPENDENT" in response:
                return "DEPENDENT"
            return "DOMAIN" if self._looks_domain_related(q) else "GENERAL"
        except Exception:
            return "DOMAIN" if self._looks_domain_related(q) else "GENERAL"

    def _clean_rewrite(self, rewrite: str, original: str) -> str:
        clean = re.sub(r"^(Rewritten Question:|Rewritten:|Question:)", "", rewrite, flags=re.IGNORECASE).strip()
        clean = clean.strip('"').strip("'")
        if len(clean) > max(len(original) * 4, 200):
            return original
        return clean if clean else original

    def _sanitize_answer_text(self, text: str) -> str:
        if not text:
            return text

        bad_starts = (
            "important:",
            "question:",
            "sources:",
            "confidence:",
            "summary:",
            "answer format",
            "summary ###",
            "key points ###",
            "steps (if applicable)",
        )

        lines = []
        for ln in text.splitlines():
            s = ln.strip()
            if not s:
                lines.append(ln)
                continue
            if s.lower().startswith(bad_starts):
                continue
            lines.append(ln)

        cleaned = "\n".join(lines).strip()
        if len(cleaned) > 2600:
            cleaned = cleaned[:2600].rstrip() + "..."
        return cleaned

    def _needs_party_names(self, query: str) -> bool:
        q = query.lower()
        return self._contains_any_term(q, ["tenant name", "tenants' name", "owner name", "landlord name", "party name", "parties"])

    def _context_mentions_party_names(self, context: str) -> bool:
        c = (context or "").lower()
        return self._contains_any_term(c, ["tenant", "landlord", "party", "parties", "owner", "name"])

    def _contains_any_term(self, text: str, terms) -> bool:
        normalized = f" {(text or '').lower()} "
        for term in terms:
            term = str(term).strip().lower()
            if not term:
                continue
            if len(term) <= 3 or " " in term or term in {"kl", "pj", "jb", "ttdi", "okr", "oug", "pwtc"}:
                if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized):
                    return True
            elif term in normalized:
                return True
        return False

    def _is_kl_related_location(self, query: str) -> bool:
        q = (query or "").lower()
        return self._contains_any_term(q, self.KL_LOCATION_TERMS)

    def _is_explicitly_non_kl_location(self, query: str) -> bool:
        q = (query or "").lower()
        if self._is_kl_related_location(q):
            return False
        return self._contains_any_term(q, self.NON_KL_LOCATION_TERMS)

    def _is_scope_help_query(self, query: str) -> bool:
        q = (query or "").lower()
        patterns = {
            "help", "scope", "what can you do", "what questions can i ask",
            "how do i use this chatbot", "what is your scope", "what do you cover"
        }
        return self._contains_any_term(q, patterns)

    def _static_greeting_reply(self, query: str) -> str:
        normalized = (query or "").lower().strip().strip("!.? ")
        return self.STATIC_GREETINGS.get(normalized, "Hello! I’m your Kuala Lumpur Real Estate Assistant.")

    def _safe_session_acknowledgement(self, query: str, user_name: str = "") -> str:
        display_name = user_name.strip()
        if not display_name:
            extracted = self._extract_name(query)
            if extracted:
                display_name = extracted
        return f"Got it, {display_name}." if display_name else "Got it."

    def _handle_session(self, query: str, result_template: Dict[str, Any]) -> str:
        extracted_name = self._extract_name(query)
        if extracted_name:
            result_template["session_updates"] = {"user_name": extracted_name}
            return f"Got it, {extracted_name}."
        return "Got it."

    def _extract_name(self, query: str) -> str:
        try:
            extracted_name = self.llm.complete(self.session_prompt.format(query_str=query)).text.strip()
            extracted_name = re.sub(r"[^\w\s]", "", extracted_name)
            if extracted_name and "NONE" not in extracted_name.upper() and len(extracted_name) < 20:
                return extracted_name
        except Exception:
            pass
        return ""

    def _safe_general_reply(self, query: str) -> str:
        q = (query or "").lower().strip()
        if self._is_scope_help_query(q):
            return (
                "I can answer Kuala Lumpur real estate questions based on the uploaded documents. "
                f"If the information is not in the database, I will reply exactly: {self.ADMIN_UPDATE_MESSAGE}"
            )
        if q in self.STATIC_GREETINGS:
            return self._static_greeting_reply(q)
        return self.ADMIN_UPDATE_MESSAGE

    def _rewrite_dependent_query(self, query: str, history: List[str]) -> str:
        if not history:
            return self.ADMIN_UPDATE_MESSAGE

        normalized_query = self._normalize_query(query)

        if self._looks_domain_related(normalized_query):
            return normalized_query

        if self._contains_any_term(normalized_query, ["give more detail", "elaborate", "explain more", "more detail", "clearer"]):
            for item in reversed(history[-6:]):
                if self._looks_domain_related(item):
                    return self._normalize_query(item)

        history_str = "\n".join(history[-7:])
        try:
            raw_rewrite = self.llm.complete(
                self.multiquery_prompt.format(history_str=history_str, query_str=normalized_query)
            ).text.strip()
            search_query = self._clean_rewrite(raw_rewrite, normalized_query)
        except Exception:
            return self.ADMIN_UPDATE_MESSAGE

        if not self._looks_domain_related(search_query) and not self._is_kl_related_location(search_query):
            return self.ADMIN_UPDATE_MESSAGE

        return search_query

    def _build_context_from_nodes(self, nodes: List[Any]) -> str:
        bad_prefixes = ("question:", "important:", "tips:", "note:", "sources:", "confidence:")
        context_parts: List[str] = []

        for node in nodes:
            text = node.get_content()
            clean_lines = []
            for line in text.splitlines():
                if line.strip().lower().startswith(bad_prefixes):
                    continue
                clean_lines.append(line)
            cleaned_text = "\n".join(clean_lines).strip()
            context_parts.append(cleaned_text[:1100])

        return "\n\n---\n\n".join(context_parts)

    def _has_relevant_coverage(self, query: str, context: str) -> bool:
        q = (query or "").lower()
        c = (context or "").lower().strip()

        if not c:
            return False

        topic_checks = [
            (["spa", "sale and purchase"], ["sale and purchase", "spa"]),
            (["mot", "memorandum of transfer"], ["memorandum of transfer", "mot"]),
            (["booking fee"], ["booking fee"]),
            (["deposit"], ["deposit", "earnest deposit", "security deposit"]),
            (["termination"], ["terminate", "termination", "notice"]),
            (["commission", "agent fee"], ["commission", "agency fee", "agent fee"]),
            (["rental", "rent", "tenancy"], ["rental", "rent", "tenancy"]),
            (["valuation", "market value"], ["valuation", "market value"]),
            (["loan", "mortgage", "financing"], ["loan", "mortgage", "financing"]),
            (["title"], ["title", "strata title", "individual title"]),
            (["quit rent", "cukai tanah"], ["quit rent", "cukai tanah"]),
            (["assessment", "cukai pintu"], ["assessment", "cukai pintu"]),
            (["developer"], ["developer"]),
            (["property"], ["property", "real estate", "house", "condo", "apartment"]),
            (["buy a house", "buy house", "how to buy"], ["title search", "stamp duty", "loan", "purchase", "market value"]),
        ]

        for q_terms, c_terms in topic_checks:
            if self._contains_any_term(q, q_terms):
                return self._contains_any_term(c, c_terms)

        if self._is_kl_related_location(q):
            return self._is_kl_related_location(c) or self._contains_any_term(
                c, ["kuala lumpur", "kl", "property", "real estate", "house", "condo", "rental", "sale"]
            )

        keywords = [
            w for w in re.findall(r"\b[a-zA-Z]{4,}\b", q)
            if w not in {"what", "when", "where", "which", "about", "there", "their", "please", "clearer", "detail", "more"}
        ]
        overlap = sum(1 for w in keywords if w in c)
        return overlap >= 1 if keywords else False

    def _literal_output_prompt(self, text: str) -> str:
        return f"Output EXACTLY the following text and nothing else:\n{text}\n"

    def _enforce_safe_output(self, text: str) -> str:
        cleaned = self._sanitize_answer_text(text)
        if not cleaned:
            return self.ADMIN_UPDATE_MESSAGE
        if self.ADMIN_UPDATE_MESSAGE.lower() in cleaned.lower():
            return self.ADMIN_UPDATE_MESSAGE

        banned_markers = [
            "not found in the provided documents",
            "i don't know",
            "cannot determine",
            "need clarification",
            "which document",
            "which clause",
            "please clarify",
            "dear admin",
            "best regards",
            "i hope this message finds you well",
            "kindly request",
            "sincerely",
        ]
        lowered = cleaned.lower()
        if any(marker in lowered for marker in banned_markers):
            return self.ADMIN_UPDATE_MESSAGE

        return cleaned

    def _compute_bleu_like(self, answer: str, evidence_text: str) -> float:
        ans_tokens = re.findall(r"\b\w+\b", (answer or "").lower())
        ev_tokens = re.findall(r"\b\w+\b", (evidence_text or "").lower())
        if not ans_tokens or not ev_tokens:
            return 0.0

        ans_counts = Counter(ans_tokens)
        ev_counts = Counter(ev_tokens)
        overlap = sum(min(count, ev_counts.get(tok, 0)) for tok, count in ans_counts.items())
        precision = overlap / max(len(ans_tokens), 1)
        bp = min(1.0, len(ev_tokens) / max(len(ans_tokens), 1))
        return round(precision * bp, 4)

    # -------------------------
    # Document text store
    # -------------------------
    def _save_doc_text(self, file_name: str, text: str) -> None:
        if not file_name:
            return
        text = (text or "").strip()
        if not text:
            return

        with db() as conn:
            conn.execute(
                """
                INSERT INTO doc_texts(file_name, content_text, updated_at)
                VALUES(?,?,?)
                ON CONFLICT(file_name) DO UPDATE SET
                    content_text=excluded.content_text,
                    updated_at=excluded.updated_at
                """,
                (file_name, text, datetime.now().isoformat()),
            )

    def _load_doc_text(self, file_name: str) -> str:
        with db() as conn:
            row = conn.execute(
                "SELECT content_text FROM doc_texts WHERE file_name=?",
                (file_name,),
            ).fetchone()
            return (row["content_text"] if row and row["content_text"] else "") or ""

    def _delete_doc_text(self, file_name: str) -> None:
        with db() as conn:
            conn.execute("DELETE FROM doc_texts WHERE file_name=?", (file_name,))

    def _extract_text_from_file(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()

        if ext == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore
                reader = PdfReader(path)
                parts = []
                for page in reader.pages:
                    parts.append(page.extract_text() or "")
                return "\n".join(parts)
            except Exception:
                pass

        if ext == ".docx":
            try:
                import docx  # type: ignore
                d = docx.Document(path)
                return "\n".join(p.text for p in d.paragraphs)
            except Exception:
                pass

        try:
            with open(path, "rb") as f:
                raw = f.read()
            try:
                return raw.decode("utf-8", errors="ignore")
            except Exception:
                return raw.decode("latin-1", errors="ignore")
        except Exception:
            return ""

    def _safe_filename(self, filename: str) -> str:
        base = os.path.basename(filename or "uploaded_file")
        base = base.replace("..", "")
        base = re.sub(r"[^A-Za-z0-9._ -]", "_", base)
        return base[:120]

    def ingest_file(self, filename: str, content: bytes) -> str:
        filename = self._safe_filename(filename)
        suffix = os.path.splitext(filename)[1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            print(f" [CRAG] Ingesting temp file: {tmp_path}")
            try:
                self.vector_service.delete_file(filename)
            except Exception:
                pass

            result = self.vector_service.ingest_document(tmp_path, file_name_override=filename)
            full_text = self._extract_text_from_file(tmp_path)
            self._save_doc_text(filename, full_text)
            return result
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def summarize_document(self, file_name: str, focus: Optional[str] = None, mode: str = "infographic") -> dict:
        file_name = self._safe_filename(file_name)
        doc_text = self._load_doc_text(file_name)

        if not doc_text.strip() and hasattr(self.vector_service, "get_file_chunks"):
            try:
                chunks = self.vector_service.get_file_chunks(file_name)
                if chunks:
                    doc_text = "\n\n".join(chunks)
            except Exception:
                pass

        if not doc_text.strip():
            return {
                "ok": False,
                "error": "No stored text for this document. Re-ingest the file first.",
                "file_name": file_name,
            }

        if len(doc_text) > 20000:
            doc_text = doc_text[:12000] + "\n...\n" + doc_text[-6000:]

        focus = (focus or "").strip()
        focus_line = f"FOCUS TOPICS: {focus}\n" if focus else ""

        if mode == "summary":
            sum_sys = (
                "You are a document analyst. Summarize the provided document clearly and concisely "
                "for a real estate staff member. Use ONLY the document text. No outside knowledge."
            )
            sum_usr = (
                "Write a structured summary with these sections (plain prose, no markdown heading symbols):\n"
                "OVERVIEW: one sentence describing the document.\n"
                "KEY POINTS: up to 6 bullet points of the most important clauses or concepts.\n"
                "IMPORTANT TERMS: up to 6 key terms with brief meanings.\n\n"
                f"{focus_line}"
                f"DOCUMENT TEXT:\n{doc_text}"
            )

            openai_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY", "")
            if openai_key:
                try:
                    from openai import OpenAI as _OAI
                    resp = _OAI(api_key=openai_key).chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": sum_sys},
                            {"role": "user", "content": sum_usr},
                        ],
                        temperature=0.3,
                        max_tokens=900,
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    if text:
                        return {"ok": True, "mode": "summary", "file_name": file_name, "text": text}
                except Exception as gpt_err:
                    print(f" [Summary] GPT failed ({gpt_err}), falling back to local LLM")

            fb_prompt = (
                "Summarize this document concisely. Output format:\n"
                "OVERVIEW: one sentence.\nKEY POINTS: up to 6 bullets.\nIMPORTANT TERMS: up to 6 terms.\n\n"
                f"{focus_line}DOCUMENT TEXT:\n{doc_text}"
            )
            try:
                text = self.llm.complete(fb_prompt).text.strip()
            except Exception:
                text = ""

            return {
                "ok": bool(text),
                "mode": "summary",
                "file_name": file_name,
                "text": text,
                "error": "No content returned" if not text else None,
            }

        sys_msg = (
            "You are a document analyst producing infographic-style JSON for a real estate UI. "
            "Use ONLY the provided document text. No outside knowledge. "
            "Output valid JSON only, no markdown, no commentary."
        )
        usr_msg = (
            'Output ONLY this JSON structure:\n'
            '{"title": string, "one_liner": string, '
            '"cards": [{"heading": string, "bullets": [string]}], '
            '"key_terms": [{"term": string, "meaning": string}], '
            '"quick_faq": [{"q": string, "a": string}]}\n\n'
            f"{focus_line}"
            f"DOCUMENT TEXT:\n{doc_text}"
        )

        openai_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            try:
                from openai import OpenAI as _OAI
                resp = _OAI(api_key=openai_key).chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": usr_msg},
                    ],
                    temperature=0,
                    max_tokens=1500,
                    response_format={"type": "json_object"},
                )
                obj = json.loads((resp.choices[0].message.content or "").strip())
                return {"ok": True, "mode": "infographic", "file_name": file_name, "infographic": obj}
            except Exception as gpt_err:
                print(f" [Infographic] GPT failed ({gpt_err}), falling back to local LLM")

        fb_prompt = (
            "You turn a document into an infographic JSON outline."
            " Output MUST be valid JSON only (no markdown).\n"
            '{"title": string, "one_liner": string, '
            '"cards": [{"heading": string, "bullets": [string]}], '
            '"key_terms": [{"term": string, "meaning": string}], '
            '"quick_faq": [{"q": string, "a": string}]}\n\n'
            f"{focus_line}DOCUMENT TEXT:\n{doc_text}"
        )
        try:
            raw = self.llm.complete(fb_prompt).text.strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            obj = json.loads(m.group(0) if m else raw)
            return {"ok": True, "mode": "infographic", "file_name": file_name, "infographic": obj}
        except Exception:
            return {
                "ok": False,
                "mode": "infographic",
                "file_name": file_name,
                "error": "Infographic generation failed. Please retry after updating the document text.",
            }

    def list_documents(self) -> List[str]:
        return self.vector_service.list_ingested_files()

    def delete_document(self, filename: str) -> bool:
        filename = self._safe_filename(filename)
        ok = self.vector_service.delete_file(filename)
        if ok:
            self._delete_doc_text(filename)
        return ok
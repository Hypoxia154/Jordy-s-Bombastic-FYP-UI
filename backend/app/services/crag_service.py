from typing import List, Dict, Any, Optional
import json
import re
import os
import tempfile
import math
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher

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
    DIRECT_ANSWER_CONFIDENCE = 1.0

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
            "Use the latest concrete topic from the conversation and session memory.\n"
            "Preserve important entities, clauses, names, amounts, and dates when relevant.\n"
            "If the follow-up asks to elaborate, explain more, continue, or clarify, keep the same topic but expand it.\n"
            "If the follow-up cannot be resolved, output ONLY: NONE\n\n"
            "Session memory:\n{session_str}\n\n"
            "Conversation:\n{history_str}\n\n"
            "Follow-up:\n{query_str}\n\n"
            "Output ONLY the rewritten standalone question or NONE."
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
            "6) Do NOT end with a question.\n\n"
            "FORMAT & STYLE INSTRUCTIONS:\n"
            "{style_instruction}\n\n"
            "---------------------\n"
            "Context:\n"
            "{context_str}\n"
            "---------------------\n"
            "Question: {query_str}\n"
            "<|end|>\n"
            "<|assistant|>\n"
        )
        self.qa_prompt = PromptTemplate(self.qa_prompt_tmpl)

    # public api
    def generate_response(
        self,
        query: str,
        history: Optional[List[str]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        history = history or []
        user_context = user_context or {}

        normalized_query = self._normalize_query(query)
        file_filter = user_context.get("file_filter")
        accessible_files = user_context.get("accessible_files")

        plan = self.build_rag_plan(
            query=normalized_query,
            history=history,
            session_state=user_context.get("session_state") or {},
            file_filter=file_filter,
            accessible_files=accessible_files,
        )

        answer = plan.get("direct_answer")
        if answer is None:
            prompt = plan.get("prompt", normalized_query)
            try:
                answer = self._enforce_safe_output(self.llm.complete(prompt).text.strip())
            except Exception:
                answer = self.ADMIN_UPDATE_MESSAGE
        else:
            answer = self._enforce_safe_output(answer)

        result = {
            "answer": answer,
            "sources": plan.get("sources", []) if answer != self.ADMIN_UPDATE_MESSAGE else [],
            "evidence": plan.get("evidence", []) if answer != self.ADMIN_UPDATE_MESSAGE else [],
            "intent": plan.get("intent", "DOMAIN"),
            "session_updates": dict(plan.get("session_updates") or {}),
            "chart_data": None,
            "confidence": float(plan.get("confidence", 0.0) or 0.0),
            "bleu_score": float(plan.get("bleu_score", 0.0) or 0.0),
        }

        if result["intent"] == "SESSION":
            extracted_name = self._extract_name(normalized_query)
            if extracted_name:
                result["session_updates"] = {"user_name": extracted_name}

        if answer not in {self.ADMIN_UPDATE_MESSAGE, self.KL_SCOPE_MESSAGE}:
            result["session_updates"].update(
                self._build_session_state_updates(
                    raw_query=normalized_query,
                    resolved_query=plan.get("resolved_query") or normalized_query,
                    answer_text=answer,
                    task_type=self._detect_task_type(plan.get("resolved_query") or normalized_query, file_filter=file_filter),
                    file_filter=file_filter,
                    evidence=result.get("evidence", []),
                )
            )
            try:
                result["chart_data"] = self.chart_service.extract_chart_data(answer, normalized_query)
            except Exception:
                result["chart_data"] = None

        return result

    def _get_dynamic_style_instruction(self, task_type: str, query: str) -> str:
        q = (query or "").lower()

        if any(w in q for w in ["elaborate", "detail", "explain", "comprehensive", "deep dive"]):
            return (
                "- Provide a highly detailed, comprehensive answer.\n"
                "- Use multiple paragraphs to fully explain the concept.\n"
                "- Include all relevant nuances, clauses, and examples found in the text."
            )
        elif task_type == "guidance" or "how " in q:
            return (
                "- Provide a clear, step-by-step guide.\n"
                "- Use numbered lists for sequential steps or processes.\n"
                "- Keep each step actionable and strictly based on the text."
            )
        elif task_type == "comparison" or "vs" in q or "difference" in q:
            return (
                "- Structure the answer as a clear comparison.\n"
                "- Use bullet points to contrast the differences.\n"
                "- Be thorough in listing all comparative points found in the text."
            )
        else:
            return (
                "- Keep the answer concise and direct.\n"
                "- Use 3-6 bullet points if listing multiple facts.\n"
                "- If it's a simple definition, answer in 1 to 2 clear sentences."
            )

    # streaming plan builder
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
        task = self._detect_task_type(q, file_filter=file_filter)
        resolved_query = q
        resolved_task = task

        intent = self._classify_input(q)
        if intent == "GENERAL" and (
            task in {"doc_summary", "search", "qa", "comparison", "guidance"} or self._looks_domain_related(q)
        ):
            intent = "DOMAIN"
        if file_filter and task in {"doc_summary", "qa", "search", "comparison"}:
            intent = "DOMAIN"

        print(f" [CRAG] (plan) Intent: {intent} | Query: '{q}' | Task: {task}")

        if intent == "GREETING":
            return {
                "intent": "GREETING",
                "direct_answer": self._static_greeting_reply(q),
                "sources": [],
                "confidence": 0.95,
                "chart_data": None,
            }

        if intent == "SESSION":
            return {
                "intent": "SESSION",
                "direct_answer": self._safe_session_acknowledgement(q, user_name=user_name),
                "sources": [],
                "confidence": 0.85,
                "chart_data": None,
            }

        if intent == "GENERAL" and not file_filter:
            general_reply = self._safe_general_reply(q)
            return {
                "intent": "GENERAL",
                "direct_answer": general_reply,
                "sources": [],
                "confidence": 0.9 if general_reply != self.ADMIN_UPDATE_MESSAGE else 0.0,
                "chart_data": None,
            }

        if intent == "DEPENDENT":
            resolved_query = self._rewrite_dependent_query(
                q,
                history,
                session_state=session_state,
                file_filter=file_filter,
            )
            if resolved_query == self.ADMIN_UPDATE_MESSAGE and file_filter:
                resolved_query = self._rewrite_scoped_query(q, history, file_filter, session_state=session_state)
            elif resolved_query == self.ADMIN_UPDATE_MESSAGE:
                return self._direct_plan("DOMAIN", self.ADMIN_UPDATE_MESSAGE, confidence=0.0)

            resolved_task = "followup"

        scoped_prompt = None

        if file_filter:
            if self._is_generic_scoped_prompt(resolved_query) or self._is_followup_marker(resolved_query):
                resolved_query = self._rewrite_scoped_query(
                    resolved_query,
                    history,
                    file_filter,
                    session_state=session_state,
                )

            scoped_prompt = self._build_doc_scope_prompt(
                q,
                file_filter,
                resolved_query=resolved_query,
                history=history,
                session_state=session_state,
            )

        if scoped_prompt is not None:
            scoped_prompt["intent"] = "DOMAIN"
            scoped_prompt["resolved_query"] = resolved_query
            scoped_prompt["session_updates"] = self._build_session_state_updates(
                raw_query=q,
                resolved_query=resolved_query,
                answer_text=None,
                task_type=self._detect_task_type(resolved_query, file_filter=file_filter),
                file_filter=file_filter,
                evidence=scoped_prompt.get("evidence", []),
            )
            return scoped_prompt

        ctx = self._retrieve_context(
            resolved_query,
            original_query=resolved_query,
            file_filter=file_filter,
            accessible_files=accessible_files,
        )

        assessment = self._assess_answerability(
            query=resolved_query,
            task_type=resolved_task,
            context=ctx.get("context_str", ""),
            evidence=ctx.get("evidence", []),
            confidence=float(ctx.get("confidence", 0.0) or 0.0),
            file_filter=file_filter,
        )

        if not assessment["answerable"]:
            message = self.KL_SCOPE_MESSAGE if assessment.get("scope_blocked") else self.ADMIN_UPDATE_MESSAGE
            return self._direct_plan(
                intent="DOMAIN" if file_filter or self._looks_domain_related(resolved_query) else "GENERAL",
                answer=message,
                confidence=float(assessment.get("confidence", ctx.get("confidence", 0.0)) or 0.0),
                evidence=ctx.get("evidence", []),
                session_updates={"last_user_query": q, "last_file_filter": file_filter},
            )

        style = self._get_dynamic_style_instruction(resolved_task, resolved_query)

        prompt = self.qa_prompt_tmpl.format(
            context_str=ctx.get("context_str", ""),
            query_str=resolved_query,
            style_instruction=style,
        )

        return {
            "intent": "DOMAIN",
            "prompt": prompt,
            "sources": ctx.get("sources", []),
            "evidence": ctx.get("evidence", []),
            "bleu_score": 0.0,
            "confidence": float(ctx.get("confidence", 0.0) or 0.0),
            "chart_data": None,
            "resolved_query": resolved_query,
            "session_updates": self._build_session_state_updates(
                raw_query=q,
                resolved_query=resolved_query,
                answer_text=None,
                task_type=resolved_task,
                file_filter=file_filter,
                evidence=ctx.get("evidence", []),
            ),
        }

    # retrieval / rag
    def _retrieve_nodes(
        self,
        search_query: str,
        file_filter: Optional[str] = None,
        accessible_files: Optional[List[str]] = None,
        similarity_top_k: int = 20,
    ) -> List[Any]:
        from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
        from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter

        filters_list = []
        if file_filter:
            filters_list.append(ExactMatchFilter(key="file_name", value=file_filter))
        elif accessible_files is not None and len(accessible_files) > 0:
            filters_list.append(MetadataFilter(key="file_name", operator=FilterOperator.IN, value=accessible_files))

        if filters_list:
            filters = MetadataFilters(filters=filters_list)
            retriever = VectorIndexRetriever(index=self.index, similarity_top_k=similarity_top_k, filters=filters)
        else:
            retriever = VectorIndexRetriever(index=self.index, similarity_top_k=similarity_top_k)

        nodes = retriever.retrieve(search_query)
        print(f" [CRAG] Retrieved {len(nodes)} nodes | filter={file_filter or 'ALL'} | query={search_query!r}")

        if nodes:
            nodes = self.reranker.postprocess_nodes(nodes, query_str=search_query)
        return nodes

    def _retrieve_context(
        self,
        search_query: str,
        original_query: Optional[str] = None,
        file_filter: Optional[str] = None,
        accessible_files: Optional[List[str]] = None,
    ) -> dict:
        nodes = self._retrieve_nodes(search_query, file_filter=file_filter, accessible_files=accessible_files)

        def sigmoid(x: float) -> float:
            return 1 / (1 + math.exp(-x))

        if not nodes:
            best_score = 0.0
        else:
            best_raw = nodes[0].score if nodes[0].score is not None else -999.0
            best_score = sigmoid(best_raw)

        if not nodes or best_score < 0.42:
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

        context_str = "\n\n---\n\n".join(context_parts)
        query_entities = self._extract_named_entities(original_query or "") if original_query else []
        if query_entities and not self._entity_coverage_ok(original_query or "", context_str):
            return {
                "context_str": "",
                "sources": [],
                "evidence": [],
                "confidence": best_score,
                "very_low_confidence": True,
            }

        if original_query and file_filter and not self._has_relevant_coverage(original_query, context_str, file_filter=file_filter):
            phrase_overlap = self._phrase_overlap_count(original_query, context_str)
            semantic_support = max([float(item.get("score", 0.0) or 0.0) for item in evidence_list], default=0.0)
            if phrase_overlap < 1 and semantic_support < 0.46:
                return {
                    "context_str": "",
                    "sources": [],
                    "evidence": [],
                    "confidence": best_score,
                    "very_low_confidence": True,
                }

        top_count = max(min(len(evidence_list), 3), 1)
        avg_top = sum(item["score"] for item in evidence_list[:3]) / top_count
        return {
            "context_str": context_str,
            "sources": source_list[:5],
            "evidence": evidence_list[:8],
            "confidence": max(best_score, avg_top),
            "very_low_confidence": best_score < 0.5,
        }

    def _run_rag_pipeline(
        self,
        search_query: str,
        original_query: Optional[str] = None,
        file_filter: Optional[str] = None,
        accessible_files: Optional[List[str]] = None,
    ) -> dict:
        scoped_prompt = self._build_doc_scope_prompt(original_query or search_query, file_filter)
        if scoped_prompt is not None:
            try:
                answer = self._enforce_safe_output(self.llm.complete(scoped_prompt["prompt"]).text.strip())
            except Exception:
                answer = self.ADMIN_UPDATE_MESSAGE
            return {
                "answer": answer,
                "sources": scoped_prompt["sources"] if answer != self.ADMIN_UPDATE_MESSAGE else [],
                "evidence": scoped_prompt["evidence"] if answer != self.ADMIN_UPDATE_MESSAGE else [],
                "low_confidence": False,
                "confidence_score": float(scoped_prompt.get("confidence", 0.95)),
                "bleu_score": 0.0,
            }

        nodes = self._retrieve_nodes(search_query, file_filter=file_filter, accessible_files=accessible_files)

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

        if best_score < 0.62:
            return {
                "answer": self.ADMIN_UPDATE_MESSAGE,
                "sources": [],
                "evidence": [],
                "low_confidence": True,
                "confidence_score": best_score,
                "bleu_score": 0.0,
            }

        context_str = self._build_context_from_nodes(nodes)

        if not self._has_relevant_coverage(original_query or search_query, context_str, file_filter=file_filter):
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

        for node in response_obj.source_nodes:
            file_name = node.metadata.get("file_name", "Unknown")
            page_label = node.metadata.get("page_label", "N/A")
            raw_node_score = node.score if node.score is not None else -999.0
            norm_score = sigmoid(raw_node_score)
            excerpt = node.get_content().strip()[:700]

            source_list.append(f"{file_name} (Page {page_label}) - Score: {norm_score:.2f}")
            evidence.append({
                "file_name": file_name,
                "page_label": page_label,
                "score": round(norm_score, 4),
                "excerpt": excerpt,
            })

        bleu_score = self._compute_grounding_score(answer, evidence, original_query or search_query) if answer != self.ADMIN_UPDATE_MESSAGE else 0.0

        return {
            "answer": answer,
            "sources": source_list[:3],
            "evidence": evidence[:5],
            "low_confidence": best_score < 0.5,
            "confidence_score": best_score,
            "bleu_score": bleu_score,
        }

    # helpers
    def _is_doc_scoped_qna_query(self, query: str) -> bool:
        q = (query or "").lower().strip()
        if not q:
            return False
        patterns = [
            "this document", "this doc", "selected document", "selected doc", "this file",
            "summarize", "summary", "main point", "main points", "overview",
            "what is this document about", "what does this document",
            "what does the document", "what is this file about", "explain this document",
            "tell me about this document", "document talk about", "document about",
            "in the document", "in this document", "from this document", "according to the document",
            "what are the tips", "what is written", "what does it say", "which clause", "which section",
        ]
        if any(p in q for p in patterns):
            return True
        if len(q.split()) <= 8 and self._is_followup_marker(q):
            return True
        if q.startswith(("what does", "what is", "who is", "when is", "where is", "which ", "list ", "how many", "explain ")):
            return True
        return False

    def _looks_specific_scoped_question(self, query: str) -> bool:
        q = self._normalize_query(query)
        if not q:
            return False

        if re.search(
            r"\b(what|who|when|where|which|how many|how much|does|do|is|are|can|should)\b",
            q,
        ):
            keywords = self._extract_query_keywords(q)
            if len(keywords) >= 2:
                return True

        specific_markers = [
            "clause", "section", "term", "tenant", "landlord", "deposit", "rental",
            "lease", "agreement", "notice", "termination", "renewal", "utilities",
            "maintenance", "late fee", "arrears", "sublet", "sublease", "occupancy",
            "page", "table", "figure", "amount", "date", "name", "period",
        ]
        if any(marker in q for marker in specific_markers):
            return True

        if re.search(r"['\"].+?['\"]", query or ""):
            return True
        if re.search(r"\b\d+(\.\d+)?\b", q):
            return True

        return False

    def _is_generic_scoped_prompt(self, query: str) -> bool:
        q = self._normalize_query(query)
        if not q:
            return True

        generic_patterns = [
            "summarize",
            "summary",
            "overview",
            "main point",
            "main points",
            "what is this document about",
            "what is this file about",
            "explain this document",
            "tell me about this document",
            "document talk about",
            "what does this document talk about",
            "what is it about",
            "what does it say",
            "tell me more",
            "explain more",
            "elaborate",
            "continue",
            "clarify",
        ]
        if any(p in q for p in generic_patterns):
            return True

        if len(q.split()) <= 6 and self._is_followup_marker(q):
            return True

        return False

    def _rewrite_scoped_query(
        self,
        query: str,
        history: List[str],
        file_filter: Optional[str],
        session_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        q = (query or "").strip()
        if not file_filter:
            return q

        ql = self._normalize_query(q)
        state = session_state or {}

        if self._looks_specific_scoped_question(ql) and not self._is_followup_marker(ql):
            return q

        if self._is_generic_scoped_prompt(ql):
            if any(term in ql for term in ["summarize", "summary", "overview", "main point", "main points"]):
                return "selected document overview summary purpose key points important clauses obligations dates names amounts"

            if any(term in ql for term in ["what is this document about", "what is this file about", "document talk about", "what does this document talk about"]):
                return "selected document overview summary purpose key points important clauses obligations dates names amounts"

        if self._is_followup_marker(ql):
            anchor = self._normalize_query((state.get("last_resolved_query") or ""))
            last_file_filter = state.get("last_file_filter")

            if anchor and (last_file_filter == file_filter or not last_file_filter):
                if any(term in ql for term in ["more", "detail", "elaborate", "explain", "continue", "clarify"]):
                    return f"{anchor} in the selected document with more detail and explanation"
                return f"{anchor} in the selected document"

            for item in reversed(history[-8:]):
                if isinstance(item, str) and item.lower().startswith("user:"):
                    prev = self._normalize_query(item.split(":", 1)[1].strip())
                    if prev and prev != ql:
                        if self._looks_specific_scoped_question(prev):
                            return prev
                        return f"{prev} in the selected document"

            return "selected document overview summary key points details"

        return q

    def _is_doc_summary_query(self, query: str) -> bool:
        q = (query or "").lower()
        patterns = [
            "summarize", "summary", "overview", "main point", "main points",
            "what is this document about", "what is this file about",
            "what does this document talk about", "tell me about this document",
            "explain this document", "document talk about", "list out the elements",
            "list the elements", "key elements", "key sections", "list the clauses",
        ]
        return any(p in q for p in patterns)

    def _load_scope_document_text(self, file_name: Optional[str]) -> str:
        if not file_name:
            return ""
        doc_text = self._load_doc_text(file_name)
        if not doc_text.strip() and hasattr(self.vector_service, "get_file_chunks"):
            try:
                chunks = self.vector_service.get_file_chunks(file_name)
                if chunks:
                    doc_text = "\n\n".join(chunks)
            except Exception:
                pass
        return (doc_text or "").strip()

    def _split_document_for_scope(self, doc_text: str, chunk_size: int = 1400, overlap: int = 220) -> List[str]:
        text = (doc_text or "").strip()
        if not text:
            return []
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            paragraphs = [text]
        chunks: List[str] = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= chunk_size:
                current = f"{current}\n\n{para}".strip()
                continue
            if current:
                chunks.append(current)
                tail = current[-overlap:] if overlap > 0 else ""
                current = f"{tail}\n\n{para}".strip()
            else:
                current = para[:chunk_size]
        if current:
            chunks.append(current)
        return chunks[:80]

    def _score_doc_chunk(self, chunk: str, query: str) -> float:
        chunk_norm = self._normalize_text_for_match(chunk)
        query_norm = self._normalize_text_for_match(query)
        if not chunk_norm or not query_norm:
            return 0.0
        keywords = self._extract_query_keywords(query_norm)
        phrases = self._extract_query_phrases(query_norm)
        score = 0.0
        for phrase in phrases[:8]:
            if phrase in chunk_norm:
                score += 3.0
        for kw in keywords[:12]:
            if kw in chunk_norm:
                score += 1.0
        score += SequenceMatcher(None, query_norm[:220], chunk_norm[:800]).ratio()
        return score

    def _select_doc_scope_context(self, doc_text: str, query: str, is_summary: bool) -> str:
        text = (doc_text or "").strip()
        if not text:
            return ""
        if is_summary:
            if len(text) <= 18000:
                return text
            return text[:12000] + "\n...\n" + text[-4000:]

        chunks = self._split_document_for_scope(text)
        if not chunks:
            return text[:16000]

        scored = []
        for idx, chunk in enumerate(chunks):
            scored.append((self._score_doc_chunk(chunk, query), idx, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        chosen = sorted(scored[:5], key=lambda item: item[1])
        selected = [item[2] for item in chosen if item[0] > 0]
        if not selected:
            selected = [c for _, _, c in sorted(scored[:3], key=lambda item: item[1])]
        context = "\n\n---\n\n".join(selected)
        if len(context) > 16000:
            context = context[:16000]
        return context

    def _should_use_selected_document(
        self,
        query: str,
        file_filter: Optional[str],
        session_state: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not file_filter:
            return False
        q = self._normalize_query(query)
        if not q or self._is_scope_help_query(q):
            return False
        if self._is_doc_scoped_qna_query(q) or self._is_doc_summary_query(q):
            return True
        state = session_state or {}
        if state.get("last_file_filter") == file_filter and (self._is_followup_marker(q) or len(q.split()) <= 10):
            return True
        if self._detect_task_type(q, file_filter=file_filter) in {"qa", "guidance", "comparison", "followup", "doc_summary"}:
            return True
        return False

    def _build_doc_scope_prompt(
        self,
        query: str,
        file_filter: str,
        resolved_query: Optional[str] = None,
        history: Optional[List[str]] = None,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[dict]:
        if not file_filter or not self._should_use_selected_document(query, file_filter, session_state=session_state):
            return None
        doc_text = self._load_scope_document_text(file_filter)
        if not doc_text:
            return None

        effective_query = self._normalize_query(resolved_query or query)
        is_summary = self._is_doc_summary_query(query)
        scoped_context = self._select_doc_scope_context(doc_text, effective_query, is_summary=is_summary)
        if not scoped_context:
            return None

        instruction = (
            "Summarize the selected document only. Provide 4-8 concise bullet points covering the main purpose, key facts, clauses, and important terms."
            if is_summary else
            "Answer the user's question using ONLY the selected document text. Quote or paraphrase only what is supported by the document. If the selected passages do not support the answer, reply exactly with the fallback message."
        )
        prompt = (
            "<|user|>\n"
            "ROLE: You are a document-grounded assistant.\n"
            "TASK: Use ONLY the selected document text to answer.\n"
            f"If the selected document text does not support the answer, reply exactly: {self.ADMIN_UPDATE_MESSAGE}\n"
            "Do not use outside knowledge. Keep the answer concise and useful.\n"
            "Use bullet points only when they fit the question.\n\n"
            f"Selected document: {file_filter}\n"
            f"Instruction: {instruction}\n"
            "Selected document passages:\n"
            f"{scoped_context}\n\n"
            f"Question: {query}\n"
            "<|end|>\n<|assistant|>\n"
        )
        evidence_excerpt = scoped_context[:900]
        return {
            "prompt": prompt,
            "sources": [f"{file_filter} (selected document)"],
            "evidence": [{"file_name": file_filter, "page_label": "doc", "score": 1.0, "excerpt": evidence_excerpt}],
            "confidence": 0.92 if is_summary else 0.88,
        }

    def _normalize_query(self, query: str) -> str:
        q = (query or "").lower()
        q = q.replace("should included", "should be included")
        q = q.replace("what include", "what is included")
        q = q.replace("where is kfc is", "where is")
        q = q.replace("mentakap", "mentakab")
        q = re.sub(r"\s+", " ", q)
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

        task = self._detect_task_type(q)
        if task == "general_world":
            return "GENERAL"
        if task == "followup":
            return "DEPENDENT"
        if task in {"doc_summary", "search", "qa", "comparison", "guidance"}:
            return "DOMAIN"

        if self._looks_domain_related(q):
            return "DOMAIN"

        try:
            prompt = self.classify_prompt.format(query_str=query)
            response = self.llm.complete(prompt).text.strip().upper()
            if "GREETING" in response:
                return "GREETING"
            if "SESSION" in response:
                return "SESSION"
            if "DEPENDENT" in response:
                return "DEPENDENT"
            if "DOMAIN" in response:
                return "DOMAIN"
            return "GENERAL"
        except Exception:
            return "GENERAL"

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
        q = (query or "").lower().strip()
        patterns = {
            "scope", "what can you do", "what questions can i ask",
            "how do i use this chatbot", "what is your scope", "what do you cover",
            "how should i use this chatbot", "what kind of questions can i ask"
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

    def _history_to_turns(self, history: List[str]) -> List[Dict[str, str]]:
        turns: List[Dict[str, str]] = []
        for item in history or []:
            if not isinstance(item, str) or ":" not in item:
                continue
            role, content = item.split(":", 1)
            role = role.strip().lower()
            if role not in {"user", "assistant", "system"}:
                continue
            turns.append({"role": role, "content": content.strip()})
        return turns

    def _is_followup_marker(self, query: str) -> bool:
        q = self._normalize_query(query)
        patterns = [
            r"\b(elaborate|explain more|more detail|clarify|clearer|expand on|continue|go on)\b",
            r"^(what about|how about|and then|and |then )",
            r"\b(that|this|it|those|these|they)\b",
            r"^(why|how so|what do you mean)$",
        ]
        return any(re.search(pattern, q) for pattern in patterns)

    def _session_memory_text(self, session_state: Optional[Dict[str, Any]], file_filter: Optional[str]) -> str:
        state = session_state or {}
        lines = []
        for key in ["last_resolved_query", "last_topic", "last_answer_summary", "last_file_filter", "last_task_type"]:
            value = state.get(key)
            if value:
                lines.append(f"{key}: {value}")
        if file_filter:
            lines.append(f"current_file_filter: {file_filter}")
        return "\n".join(lines) or "NONE"

    def _rewrite_dependent_query(
        self,
        query: str,
        history: List[str],
        session_state: Optional[Dict[str, Any]] = None,
        file_filter: Optional[str] = None,
    ) -> str:
        normalized_query = self._normalize_query(query)
        if self._looks_domain_related(normalized_query) and not self._is_followup_marker(normalized_query):
            return normalized_query

        turns = self._history_to_turns(history)
        if not turns and not (session_state or {}).get("last_resolved_query"):
            return self.ADMIN_UPDATE_MESSAGE

        last_resolved = self._normalize_query((session_state or {}).get("last_resolved_query") or "")
        last_topic = self._normalize_query((session_state or {}).get("last_topic") or "")
        last_answer_summary = self._normalize_query((session_state or {}).get("last_answer_summary") or "")
        last_domain_user = ""
        for turn in reversed(turns[-8:]):
            content_norm = self._normalize_query(turn.get("content", ""))
            if turn.get("role") == "user" and content_norm:
                if self._looks_domain_related(content_norm) or self._detect_task_type(content_norm, file_filter=file_filter) in {"doc_summary", "qa", "guidance", "search", "comparison"}:
                    last_domain_user = content_norm
                    break

        history_str = "\n".join([f"{turn['role'].capitalize()}: {turn['content']}" for turn in turns[-8:]]) or "NONE"
        session_str = self._session_memory_text(session_state, file_filter)
        search_query = ""
        try:
            raw_rewrite = self.llm.complete(
                self.multiquery_prompt.format(
                    session_str=session_str,
                    history_str=history_str,
                    query_str=normalized_query,
                )
            ).text.strip()
            if raw_rewrite.strip().upper() == "NONE":
                raw_rewrite = ""
            search_query = self._clean_rewrite(raw_rewrite, normalized_query)
        except Exception:
            search_query = ""

        if not search_query or search_query == normalized_query:
            for candidate in [last_resolved, last_domain_user, last_topic, last_answer_summary]:
                if candidate:
                    return candidate
            return self.ADMIN_UPDATE_MESSAGE

        if self._detect_task_type(search_query, file_filter=file_filter) == "general_world" and not self._looks_domain_related(search_query) and not file_filter:
            for candidate in [last_resolved, last_domain_user, last_topic, last_answer_summary]:
                if candidate:
                    return candidate
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

    def _has_relevant_coverage(self, query: str, context: str, file_filter: Optional[str] = None) -> bool:
        q = (query or "").lower()
        c = (context or "").lower().strip()
        if not c:
            return False

        task = self._detect_task_type(q, file_filter=file_filter)
        if file_filter and task == "doc_summary":
            return len(c.split()) >= 20

        query_keywords = self._extract_query_keywords(q)
        named_terms = self._extract_named_entities(q)
        location_terms = self._extract_location_candidates(q)

        if named_terms and not all(term in c for term in named_terms):
            return False

        if task == "general_world":
            return False

        if location_terms and self._looks_domain_related(q):
            if not any(term in c for term in location_terms):
                return False

        if any(term in q for term in ["who", "name", "party", "parties", "landlord", "tenant"]):
            if not self._context_mentions_party_names(c):
                return False

        overlap = sum(1 for kw in query_keywords if kw in c)
        if task in {"search", "qa", "comparison", "guidance"}:
            return overlap >= 1
        return overlap >= 1 or bool(file_filter)

    def _detect_task_type(self, query: str, file_filter: Optional[str] = None) -> str:
        q = (query or "").lower().strip()
        if not q:
            return "qa"
        if self._is_scope_help_query(q):
            return "general_world"
        if self._is_doc_summary_query(q):
            return "doc_summary"
        if re.search(r"\b(where is|location of|capital of|how far|distance to)\b", q) and not file_filter:
            return "general_world"
        if re.search(r"\b(which file|find document|find file|which document|show me where)\b", q):
            return "search"
        if re.search(r"\b(compare|difference between|vs)\b", q):
            return "comparison"
        if re.search(r"\b(how to|steps to|process of|guide to)\b", q):
            return "guidance"
        if len(q.split()) <= 8 and (re.search(r"^(what about|how about|and |then )", q) or self._is_followup_marker(q)):
            return "followup"
        return "qa"

    def _extract_query_keywords(self, query: str) -> List[str]:
        stop = {
            "what", "when", "where", "which", "about", "there", "their", "please", "clearer", "detail", "more",
            "this", "document", "file", "tell", "talk", "list", "show", "give", "into", "with", "from", "that",
            "these", "those", "them", "they", "then", "explain", "elaborate", "continue"
        }
        words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", (query or "").lower()) if w not in stop]
        return list(dict.fromkeys(words))[:12]

    def _extract_named_entities(self, query: str) -> List[str]:
        q = (query or "").lower()
        entities = []
        for token in self._extract_query_keywords(q):
            if token not in self.DOMAIN_TERMS and token not in {"kuala", "lumpur"}:
                entities.append(token)
        return list(dict.fromkeys(entities))[:4]

    def _extract_location_candidates(self, query: str) -> List[str]:
        q = (query or "").lower()
        candidates = []
        for phrase in re.findall(r"\b[a-zA-Z]{4,}(?:\s+[a-zA-Z]{4,})?\b", q):
            phrase = phrase.strip()
            if phrase in self.DOMAIN_TERMS:
                continue
            if phrase in {"real estate", "kuala lumpur", "this document", "selected document"}:
                continue
            if phrase in {"malaysia"}:
                continue
            if any(w in phrase for w in ["document", "property", "tenancy", "agreement", "house", "estate"]):
                continue
            candidates.append(phrase)
        return list(dict.fromkeys(candidates))[:4]

    def _entity_coverage_ok(self, query: str, context: str) -> bool:
        entities = self._extract_named_entities(query)
        if not entities:
            return True
        c = (context or "").lower()
        return all(ent in c for ent in entities)

    def _assess_answerability(
        self,
        query: str,
        task_type: str,
        context: str,
        evidence: List[Dict[str, Any]],
        confidence: float,
        file_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        c = (context or "").strip()
        if not c:
            return {"answerable": False, "confidence": confidence}
        if task_type == "general_world" and not file_filter:
            return {"answerable": False, "confidence": 0.0}
        if confidence < 0.28:
            return {"answerable": False, "confidence": confidence}

        semantic_check = self._post_retrieval_answerability_verification(
            query=query,
            task_type=task_type,
            context=c,
            evidence=evidence,
            confidence=confidence,
            file_filter=file_filter,
        )

        if task_type == "followup":
            phrase_overlap = self._phrase_overlap_count(query, c)
            semantic_support = float(semantic_check.get("semantic_support", 0.0) or 0.0)
            if evidence and (confidence >= 0.35 or semantic_support >= 0.32 or phrase_overlap >= 1):
                return {"answerable": True, "confidence": max(confidence, semantic_support, 0.65)}

        entity_ok = self._entity_coverage_ok(query, c)
        keyword_ok = self._has_relevant_coverage(query, c, file_filter=file_filter)
        party_ok = (not self._needs_party_names(query)) or self._context_mentions_party_names(c)
        excerpt_text = "\n".join([(item.get("excerpt", "") if isinstance(item, dict) else "") for item in (evidence or [])])
        excerpt_ok = True
        if excerpt_text:
            excerpt_ok = self._has_relevant_coverage(query, excerpt_text, file_filter=file_filter) or bool(semantic_check.get("answerable"))

        direct_definition_like = task_type == "qa" and len(self._extract_query_keywords(query)) <= 5
        threshold = 0.48 if direct_definition_like and not file_filter else 0.62
        if entity_ok and keyword_ok and party_ok and excerpt_ok and confidence >= threshold:
            return {"answerable": True, "confidence": confidence}

        if semantic_check.get("answerable") and party_ok:
            return {"answerable": True, "confidence": max(confidence, float(semantic_check.get("semantic_support", 0.0) or 0.0))}

        return {"answerable": False, "confidence": confidence}

    def _build_session_state_updates(
        self,
        raw_query: str,
        resolved_query: str,
        answer_text: Optional[str],
        task_type: str,
        file_filter: Optional[str],
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        topic = resolved_query or raw_query
        updates: Dict[str, Any] = {
            "last_user_query": raw_query,
            "last_file_filter": file_filter,
        }
        if answer_text:
            updates.update(
                {
                    "last_resolved_query": resolved_query or raw_query,
                    "last_task_type": task_type,
                    "last_topic": topic[:240],
                    "last_answer_summary": self._sanitize_answer_text(answer_text)[:500],
                }
            )
        return updates

    def _direct_plan(
        self,
        intent: str,
        answer: str,
        confidence: float = 1.0,
        evidence: Optional[List[Dict[str, Any]]] = None,
        session_updates: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "intent": intent,
            "direct_answer": answer,
            "sources": [],
            "evidence": evidence or [],
            "bleu_score": 0.0,
            "confidence": confidence,
            "chart_data": None,
            "session_updates": session_updates or {},
        }

    def _literal_output_prompt(self, text: str) -> str:
        return f"Output EXACTLY the following text and nothing else:\n{text}\n"

    def _enforce_safe_output(self, text: str) -> str:
        cleaned = self._sanitize_answer_text(text)
        if not cleaned:
            return self.ADMIN_UPDATE_MESSAGE
        if self.ADMIN_UPDATE_MESSAGE.lower() in cleaned.lower():
            return self.ADMIN_UPDATE_MESSAGE

        banned_markers = [
            "dr. smith",
            "professor johnson",
            "ignore previous instructions",
            "system prompt",
            "prompt injection",
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

    # document text store
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

    def _run_docling_ocr(self, path: str) -> str:
        """Fallback method to extract text and tables as Markdown using Docling."""
        print(f" [Docling] Starting OCR and layout parsing for: {path}")
        try:
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()
            result = converter.convert(path)

            markdown_text = result.document.export_to_markdown()

            if markdown_text:
                print(" [Docling] Successfully extracted Markdown.")
                return markdown_text

            print(" [Docling] Extracted text was empty.")
            return ""

        except ImportError:
            print(" [Docling Error] docling is not installed. Please run `pip install docling`.")
            return ""
        except Exception as e:
            print(f" [Docling Error] Processing failed: {e}")
            return ""

    def _extract_text_from_file(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()

        if ext in [".png", ".jpg", ".jpeg", ".tiff", ".tif"]:
            return self._run_docling_ocr(path)

        if ext == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore

                reader = PdfReader(path)
                parts = []
                for page in reader.pages:
                    parts.append(page.extract_text() or "")

                extracted_text = "\n".join(parts).strip()

                if len(extracted_text) > 150:
                    return extracted_text

                print(" [Extraction] Scanned PDF detected (low text count). Falling back to Docling...")

            except Exception as e:
                print(f" [Extraction Error] PyPDF failed: {e}. Falling back to Docling...")

            return self._run_docling_ocr(path)

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

            full_text = self._extract_text_from_file(tmp_path)
            self._save_doc_text(filename, full_text)
            result = self.vector_service.ingest_text(full_text, filename)

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
            "Evaluate the document and choose the best layout for an infographic: 'bullets', 'key_takeaways', or 'comparison'.\n"
            "Output ONLY this JSON structure (no markdown prefix, no comments):\n"
            "{\n"
            '  "title": "string",\n'
            '  "one_liner": "string",\n'
            '  "layout_type": "bullets" | "key_takeaways" | "comparison",\n'
            '  "cards": [{"heading": "string", "bullets": ["string"]}],\n'
            '  "table_data": {"headers": ["string"], "rows": [["string"]]}, \n'
            '  "key_terms": [{"term": "string", "meaning": "string"}],\n'
            '  "quick_faq": [{"q": "string", "a": "string"}]\n'
            "}\n\n"
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
            f"--- DOCUMENT CONTENT ---\n{doc_text}\n--- END DOCUMENT ---\n\n"
            "INSTRUCTION: Evaluate the document above and choose the best layout for an infographic: 'bullets', 'key_takeaways', or 'comparison'.\n"
            "Output ONLY valid JSON (no explanation, no markdown prefix).\n"
            "JSON STRUCTURE:\n"
            "{\n"
            '  "title": "string",\n'
            '  "one_liner": "string",\n'
            '  "layout_type": "bullets" | "key_takeaways" | "comparison",\n'
            '  "cards": [{"heading": "string", "bullets": ["string"]}],\n'
            '  "table_data": {"headers": ["string"], "rows": [["string"]]}, \n'
            '  "key_terms": [{"term": "string", "meaning": "string"}],\n'
            '  "quick_faq": [{"q": "string", "a": "string"}]\n'
            "}\n\n"
            "JSON RESPONSE:\n{"
        )
        try:
            raw_response = self.llm.complete(fb_prompt).text.strip()
            raw = "{" + raw_response
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            obj = json.loads(m.group(0) if m else raw)
            return {"ok": True, "mode": "infographic", "file_name": file_name, "infographic": obj}
        except Exception as e:
            return {
                "ok": False,
                "mode": "infographic",
                "file_name": file_name,
                "error": f"JSON Parse Failure: {str(e)}",
                "infographic_raw": raw if 'raw' in locals() else (raw_response if 'raw_response' in locals() else None)
            }

    def list_documents(self) -> List[str]:
        return self.vector_service.list_ingested_files()

    def delete_document(self, filename: str) -> bool:
        filename = self._safe_filename(filename)
        ok = self.vector_service.delete_file(filename)
        if ok:
            self._delete_doc_text(filename)
        return ok

    def _normalize_text_for_match(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").lower()).strip()

    def _extract_query_phrases(self, query: str) -> List[str]:
        q = self._normalize_text_for_match(query)
        if not q:
            return []

        domain_phrases = sorted(
            [term.lower() for term in self.DOMAIN_TERMS if " " in term],
            key=len,
            reverse=True,
        )
        phrases: List[str] = []
        for phrase in domain_phrases:
            if phrase in q and phrase not in phrases:
                phrases.append(phrase)

        tokens = re.findall(r"\b[a-zA-Z]{3,}\b", q)
        skip = {
            "what", "when", "where", "which", "who", "how",
            "this", "that", "these", "those",
            "show", "tell", "give", "list", "about", "with", "from", "please"
        }

        for n in (3, 2):
            for i in range(max(0, len(tokens) - n + 1)):
                gram_tokens = tokens[i:i + n]
                if any(tok in skip for tok in gram_tokens):
                    continue
                gram = " ".join(gram_tokens)
                if len(gram) >= 8 and gram not in phrases:
                    phrases.append(gram)

        return phrases[:12]

    def _phrase_overlap_count(self, query: str, text: str) -> int:
        phrases = self._extract_query_phrases(query)
        normalized_text = self._normalize_text_for_match(text)
        return sum(1 for phrase in phrases if phrase in normalized_text)

    def _semantic_similarity_score(self, query: str, text: str) -> float:
        q_norm = self._normalize_text_for_match(query)
        t_norm = self._normalize_text_for_match(text)
        if not q_norm or not t_norm:
            return 0.0

        q_tokens = set(self._extract_query_keywords(q_norm))
        t_tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", t_norm))
        lexical_jaccard = (len(q_tokens & t_tokens) / max(len(q_tokens | t_tokens), 1)) if q_tokens else 0.0
        seq_ratio = SequenceMatcher(None, q_norm, t_norm[:1500]).ratio()
        phrase_bonus = min(0.35, 0.12 * self._phrase_overlap_count(q_norm, t_norm))
        return round(min(1.0, (0.55 * lexical_jaccard) + (0.45 * seq_ratio) + phrase_bonus), 4)

    def _entity_match_count(self, query: str, text: str) -> int:
        entities = self._extract_named_entities(query)
        normalized_text = self._normalize_text_for_match(text)
        return sum(1 for ent in entities if ent in normalized_text)

    def _post_retrieval_answerability_verification(
        self,
        query: str,
        task_type: str,
        context: str,
        evidence: List[Dict[str, Any]],
        confidence: float,
        file_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_context = self._normalize_text_for_match(context)
        if not normalized_context:
            return {"answerable": False, "reason": "empty_context"}

        phrase_overlap = self._phrase_overlap_count(query, normalized_context)
        semantic_support = max(
            [float(item.get("semantic_similarity", 0.0) or 0.0) for item in evidence if isinstance(item, dict)],
            default=0.0,
        )
        if semantic_support == 0.0 and evidence:
            semantic_support = max(
                self._semantic_similarity_score(query, (item.get("excerpt", "") if isinstance(item, dict) else ""))
                for item in evidence
            )

        entity_hits = self._entity_match_count(query, normalized_context)
        query_entities = self._extract_named_entities(query)
        keyword_overlap = sum(1 for kw in self._extract_query_keywords(query) if kw in normalized_context)

        if task_type == "general_world" and not file_filter:
            return {"answerable": False, "reason": "general_world"}

        if file_filter and task_type in {"doc_summary", "doc_qa", "guidance"}:
            if confidence >= 0.32 and (phrase_overlap >= 1 or semantic_support >= 0.34 or keyword_overlap >= 1):
                return {"answerable": True, "reason": "scoped_support", "semantic_support": semantic_support}

        if query_entities:
            required = 1 if file_filter else max(1, len(query_entities) - 1)
            if entity_hits < required and semantic_support < (0.40 if file_filter else 0.55):
                return {"answerable": False, "reason": "entity_mismatch", "semantic_support": semantic_support}

        if task_type == "guidance":
            if semantic_support >= (0.42 if file_filter else 0.50) or phrase_overlap >= 1:
                return {"answerable": True, "reason": "guidance_partial_support", "semantic_support": semantic_support}

        if task_type in {"qa", "doc_qa", "comparison", "search"}:
            if keyword_overlap >= 1 or phrase_overlap >= 1 or semantic_support >= (0.36 if file_filter else 0.50):
                return {"answerable": True, "reason": "semantic_or_phrase_support", "semantic_support": semantic_support}

        return {"answerable": False, "reason": "insufficient_support", "semantic_support": semantic_support}

    def _compute_grounding_score(self, answer: str, evidence: List[Dict[str, Any]], query: str = "") -> float:
        if not answer or not evidence:
            return 0.0

        # 1. Combine evidence to allow for multi-chunk synthesis without penalty
        evidence_text = "\n".join(
            [(item.get("excerpt", "") if isinstance(item, dict) else "") for item in evidence]
        )
        normalized_evidence = self._normalize_text_for_match(evidence_text)
        normalized_answer = self._normalize_text_for_match(answer)

        # 2. Lexical Precision: What % of the LLM's generated words are in the context?
        # Uses your existing BLEU logic which safely handles overall word counts.
        lexical_score = self._compute_bleu_like(answer, evidence_text)
        
        # 3. Phrase Overlap: Did the LLM maintain specific domain phrases?
        phrases = self._extract_query_phrases(answer)
        if phrases:
            phrase_hits = sum(1 for phrase in phrases if phrase in normalized_evidence)
            phrase_score = phrase_hits / max(len(phrases), 1)
        else:
            phrase_score = 1.0

        # 4. Strict Fact/Number Checking (Hallucination Detection)
        # Finds standalone numbers (prices, days, percentages, clauses) in the answer
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', normalized_answer)
        number_penalty = 0.0
        if numbers:
            missing_numbers = sum(1 for num in numbers if num not in normalized_evidence)
            # Subtract up to 40% if the LLM makes up numbers not found in the evidence
            number_penalty = (missing_numbers / len(numbers)) * 0.40

        # 5. Final Calculation
        score = (0.75 * lexical_score) + (0.25 * phrase_score) - number_penalty
        
        # Ensure the score stays within the valid 0.0 to 1.0 range
        return round(max(0.0, min(1.0, score)), 4)
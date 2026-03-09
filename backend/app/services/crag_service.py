from typing import List, Dict, Any, Union
import json
import re
import os
import tempfile

from llama_index.llms.ollama import Ollama
from llama_index.core import Settings as LlamaSettings, get_response_synthesizer, PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank


from app.core.config import settings
from app.services.vector_store import VectorService
from app.services.chart_service import ChartService
from datetime import datetime
from app.db.sqlite import db


class CRAGService:
    def __init__(self):
        print(f" [CRAG] Initializing with Model: {settings.LLM_MODEL}...")

        self.llm = Ollama(
            model=settings.LLM_MODEL,
            request_timeout=300.0,
            temperature=0.1,
            additional_kwargs={
                "num_ctx": 4096,
                "num_predict": 600,
                "stop": [
                    "<|end|>",
                    "<|user|>",
                    "<|assistant|>",
                    "---------------------",
                    "Sources:",
                    "Confidence:",
                ],
            },
        )
        LlamaSettings.llm = self.llm

        self.vector_service = VectorService()
        self.index = self.vector_service.get_index()
        self.reranker = SentenceTransformerRerank(model=settings.RERANKER_MODEL, top_n=5)

        self.chart_service = ChartService()

        # ---------------------
        # PROMPTS
        # ---------------------
        self.classify_prompt = PromptTemplate(
            "Classify the User Input into exactly one category:\n"
            "1. GREETING: (Hello, Hi, Thanks, Bye)\n"
            "2. SESSION: (User name, preferences)\n"
            "3. GENERAL: (Weather, Jokes, General Knowledge)\n"
            "4. DOMAIN: (Real Estate, Tenancy, Contracts, Rent, Property, Rights, Clauses, Obligations)\n"
            "5. DEPENDENT: (Ambiguous follow-ups)\n"
            "\n"
            "Examples:\n"
            "User: 'Hi there' -> GREETING\n"
            "User: 'My name is John' -> SESSION\n"
            "User: 'Tell me a joke' -> GENERAL\n"
            "User: 'What is the rent?' -> DOMAIN\n"
            "User: 'How much is it?' -> DEPENDENT\n"
            "User: 'Help' -> GENERAL\n"
            "\n"
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
            "Rewrite the user's follow-up question into a standalone search query.\n"
            "Use conversation context.\n"
            "Context:\n{history_str}\n\n"
            "Follow-up:\n{query_str}\n\n"
            "Output ONLY the rewritten standalone question."
        )

        # Very short + strict for GENERAL

        self.general_structured_prompt = PromptTemplate(

            "You are a helpful assistant for Malaysian real estate.\n"

            "Be concise (max 80 words). No section headers.\n"

            "Respond in 1-3 plain bullet points only.\n\n"

            "User: {query_str}\n"

        )


        # Very short greeting/session behavior
        self.greeting_prompt = PromptTemplate(
            "You are a Malaysian Real Estate Assistant.\n"
            "Reply politely in ONE sentence.\n"
            "Do NOT claim a personal name.\n\n"
            "User: {query_str}\n"
        )

        self.session_ack_prompt = PromptTemplate(
            "You are a Malaysian Real Estate Assistant.\n"
            "Acknowledge the user's info in ONE short sentence.\n"
            "Do NOT mention storing data securely.\n"
            "Do NOT mention privacy policy.\n\n"
            "User: {query_str}\n"
        )

        # DOMAIN strict prompt (short + grounded + no new questions unless missing)
        self.qa_prompt_tmpl = (
            "<|user|>\n"
            "ROLE: You are a document-grounded assistant for Malaysian real estate.\n"
            "TASK: Answer the user's question using ONLY the Context.\n\n"
            "HARD RULES:\n"
            "1) Use ONLY facts found in Context. No outside knowledge.\n"
            "2) If Context does not answer the question, say: \"Not found in the provided documents.\" then ask ONE targeted clarification.\n"
            "3) Do NOT add new topics. Do NOT add general tips.\n"
            "4) Do NOT end with a random question.\n"
            "5) Ignore irrelevant text in Context.\n\n"
            "ANSWER FORMAT:\n"

            "- Give 2-4 direct bullet points answering the question.\n"

            "- If context does not fully answer, write: Not found in the provided documents.\n"

            "- Do NOT output section headers like Answer, Evidence, or Missing.\n\n"

            "STYLE:\n"

            "- 120–170 words max.\n"
            "- Bullets only (no paragraphs).\n\n"
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
    def generate_response(self, query: str, history: List[str] = [], user_context: Dict[str, Any] = {}) -> Dict[str, Any]:
        # keep your existing non-stream flow if you still use it
        category = self._classify_input(query)
        if category == "GENERAL" and self._looks_domain_related(query):
            category = "DOMAIN"

        result_template = {
            "answer": "",
            "sources": [],
            "intent": category,
            "session_updates": {},
            "chart_data": None,
            "confidence": 1.0,
        }

        if category == "GREETING":
            result_template["answer"] = "Hello! I’m your Real Estate Assistant. How can I help?"
            return result_template

        if category == "SESSION":
            try:
                extracted_name = self.llm.complete(self.session_prompt.format(query_str=query)).text.strip()
                extracted_name = re.sub(r"[^\w\s]", "", extracted_name)
                if extracted_name and "NONE" not in extracted_name.upper() and len(extracted_name) < 20:
                    result_template["answer"] = f"Got it, {extracted_name}."
                    result_template["session_updates"] = {"user_name": extracted_name}
                else:
                    result_template["answer"] = "Got it."
            except Exception:
                result_template["answer"] = "Got it."
            return result_template

        if category == "GENERAL":
            try:
                response = self.llm.complete(self.general_structured_prompt.format(query_str=query)).text.strip()
                result_template["answer"] = self._sanitize_answer_text(response)
                result_template["confidence"] = 0.6
            except Exception:
                result_template["answer"] = "### Answer\n- I can help with tenancy agreements and property questions."
                result_template["confidence"] = 0.4
            return result_template

        # DOMAIN: normal RAG
        search_query = self._normalize_query(query)
        rag_result = self._run_rag_pipeline(search_query)

        final_answer = self._sanitize_answer_text(rag_result["answer"])
        result_template["answer"] = final_answer
        result_template["sources"] = rag_result.get("sources", [])
        result_template["confidence"] = rag_result.get("confidence_score", 1.0)
        return result_template

    # ---------------------
    # Streaming plan builder (used by crag.py)
    # ---------------------
    def build_rag_plan(self, query: str, history: list[str], session_state: dict | None = None, file_filter: str | None = None, accessible_files: list[str] | None = None) -> dict:
        q = (query or "").strip()
        session_state = session_state or {}

        last_intent = (session_state.get("last_intent") or "").upper().strip()
        user_name = (session_state.get("user_name") or "").strip()

        # 1) classify
        intent = self._classify_input(q)

        # keyword override
        if intent == "GENERAL" and self._looks_domain_related(q):
            intent = "DOMAIN"

        # ✅ requested: dependent inherits last domain
        if intent == "DEPENDENT" and last_intent == "DOMAIN":
            intent = "DOMAIN"

        print(f" [CRAG] (plan) Intent: {intent} | Last: {last_intent} | Query: '{q}'")

        # 2) greeting/session/general
        if intent == "GREETING":
            prompt = self.greeting_prompt.format(query_str=q)
            return {"intent": "GREETING", "prompt": prompt, "sources": [], "confidence": 0.9, "chart_data": None}

        if intent == "SESSION":
            # If user explicitly says "my name is X", we still want short acknowledgement
            prefix = f"{user_name}, " if user_name else ""
            prompt = self.session_ack_prompt.format(query_str=f"{prefix}{q}")
            return {"intent": "SESSION", "prompt": prompt, "sources": [], "confidence": 0.8, "chart_data": None}

        if intent == "GENERAL":
            prefix = f"{user_name}, " if user_name else ""
            prompt = self.general_structured_prompt.format(query_str=f"{prefix}{q}")
            return {"intent": "GENERAL", "prompt": prompt, "sources": [], "confidence": 0.6, "chart_data": None}

        # 3) dependent rewrite only if we didn't force DOMAIN above
        search_query = self._normalize_query(q)
        if intent == "DEPENDENT":
            if history:
                print(" [CRAG] (plan) Rewriting dependent question...")
                history_str = "\n".join(history[-7:])
                raw_rewrite = self.llm.complete(self.multiquery_prompt.format(history_str=history_str, query_str=search_query)).text.strip()
                search_query = self._clean_rewrite(raw_rewrite, search_query)

                if self._looks_domain_related(search_query):
                    intent = "DOMAIN"
                else:
                    prompt = self.general_structured_prompt.format(query_str=q)
                    return {"intent": "GENERAL", "prompt": prompt, "sources": [], "confidence": 0.5, "chart_data": None}
            else:
                prompt = (
                    "You are a helpful assistant.\n"
                    "Ask ONE short clarification question.\n\n"
                    f"User: {q}\n"
                )
                return {"intent": "DEPENDENT", "prompt": prompt, "sources": [], "confidence": 0.4, "chart_data": None}

        # 4) DOMAIN retrieval-only
        ctx = self._retrieve_context(search_query, file_filter=file_filter, accessible_files=accessible_files)

        # Very low confidence -> ask clarification
        if ctx.get("very_low_confidence"):
            prompt = (
                "Not found in the provided documents.\n"
                "Ask ONE targeted clarification (e.g., which clause/section/topic).\n\n"
                f"Question: {q}\n"
            )
            return {
                "intent": "DOMAIN",
                "prompt": prompt,
                "sources": [],
                "confidence": float(ctx.get("confidence", 0.0) or 0.0),
                "chart_data": None,
            }

        # ✅ Question-coverage guardrail:
        # If user asks about names in tenancy agreement, but context doesn't mention name/party/landlord/tenant,
        # treat as not found (prevents “encumbrance” answers).
        if self._needs_party_names(q) and not self._context_mentions_party_names(ctx.get("context_str", "")):
            prompt = (
                "Not found in the provided documents.\n"
                "Which document or clause are you referring to (e.g., Parties / Landlord / Tenant section)?\n\n"
                f"Question: {q}\n"
            )
            return {
                "intent": "DOMAIN",
                "prompt": prompt,
                "sources": ctx.get("sources", []),
                "confidence": float(ctx.get("confidence", 0.0) or 0.0),
                "chart_data": None,
            }

        prompt = self.qa_prompt_tmpl.format(context_str=ctx["context_str"], query_str=q)
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
    def _retrieve_context(self, search_query: str, file_filter: str | None = None, accessible_files: list[str] | None = None) -> dict:
        from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
        from llama_index.core.vector_stores.types import FilterOperator, MetadataFilter

        filters_list = []
        if file_filter:
            filters_list.append(ExactMatchFilter(key="file_name", value=file_filter))
        elif accessible_files is not None:
            # If no single file filter but we have access control, only allow accessible files
            # Note: exact structure depends on vector store, but usually we iterate ExactMatch or use an InFilter 
            filters_list.append(MetadataFilter(key="file_name", operator=FilterOperator.IN, value=accessible_files))

        if filters_list:
            filters = MetadataFilters(filters=filters_list)
            retriever = VectorIndexRetriever(index=self.index, similarity_top_k=20, filters=filters)
        else:
            retriever = VectorIndexRetriever(index=self.index, similarity_top_k=20)
        nodes = retriever.retrieve(search_query)
        print(f" [CRAG] (plan) Retrieved {len(nodes)} nodes")

        if nodes:
            nodes = self.reranker.postprocess_nodes(nodes, query_str=search_query)

        import math

        def sigmoid(x: float) -> float:
            return 1 / (1 + math.exp(-x))

        if not nodes:
            best_score = 0.0
        else:
            best_raw = nodes[0].score if nodes[0].score is not None else -999.0
            best_score = sigmoid(best_raw)

        print(f" [CRAG] (plan) Best Score (normalized): {best_score:.2f}")

        if not nodes or best_score < 0.15:
            return {"context_str": "", "sources": [], "confidence": best_score, "very_low_confidence": True}

        # Build context from top 5 reranked chunks (reranker top_n=5)
        context_parts: List[str] = []
        source_list: List[str] = []

        BAD_PREFIXES = ("question:", "important:", "tips:", "note:", "sources:", "confidence:")

        for node in nodes:
            text = node.get_content()
            # remove obvious junk lines from ingested PDFs
            clean_lines = []
            for line in text.splitlines():
                if line.strip().lower().startswith(BAD_PREFIXES):
                    continue
                clean_lines.append(line)
            cleaned_text = "\n".join(clean_lines).strip()

            context_parts.append(cleaned_text[:1100])

            file_name = node.metadata.get("file_name", "Unknown")
            page_label = node.metadata.get("page_label", "N/A")
            raw_node_score = node.score if node.score is not None else -999.0
            norm_score = sigmoid(raw_node_score)
            source_list.append(f"{file_name} (Page {page_label}) - Score: {norm_score:.2f}")

        return {
            "context_str": "\n\n---\n\n".join(context_parts),
            "sources": source_list[:3],
            "confidence": best_score,
            "very_low_confidence": False,
        }

    def _run_rag_pipeline(self, search_query: str) -> dict:
        retriever = VectorIndexRetriever(index=self.index, similarity_top_k=20)
        nodes = retriever.retrieve(search_query)

        if nodes:
            nodes = self.reranker.postprocess_nodes(nodes, query_str=search_query)

        nodes = nodes[:4]

        import math

        def sigmoid(x):
            return 1 / (1 + math.exp(-x))

        if not nodes:
            return {
                "answer": "Not found in the provided documents.",
                "sources": [],
                "low_confidence": True,
                "confidence_score": 0.0,
            }

        best_raw = nodes[0].score if nodes[0].score is not None else -999
        best_score = sigmoid(best_raw)

        if best_score < 0.15:
            return {
                "answer": "Not found in the provided documents.",
                "sources": [],
                "low_confidence": True,
                "confidence_score": best_score,
            }

        synthesizer = get_response_synthesizer(text_qa_template=self.qa_prompt, response_mode="compact")
        response_obj = synthesizer.synthesize(search_query, nodes=nodes)

        source_list = []
        for node in response_obj.source_nodes:
            file_name = node.metadata.get("file_name", "Unknown")
            page_label = node.metadata.get("page_label", "N/A")
            raw_node_score = node.score if node.score is not None else -999
            norm_score = sigmoid(raw_node_score)
            source_list.append(f"{file_name} (Page {page_label}) - Score: {norm_score:.2f}")

        return {
            "answer": str(response_obj),
            "sources": source_list[:3],
            "low_confidence": best_score < 0.5,
            "confidence_score": best_score,
        }

    # ---------------------
    # Helpers
    # ---------------------
    def _normalize_query(self, query: str) -> str:
        q = query.lower()
        q = q.replace("should included", "should be included")
        q = q.replace("what include", "what is included")
        return q

    def _looks_domain_related(self, query: str) -> bool:
        keywords = {
            "tenancy", "lease", "rental", "rent", "landlord", "tenant", "property",
            "agreement", "contract", "deposit", "notice", "termination", "eviction",
            "premises", "maintenance", "utility", "utilities", "inspection", "renewal",
            "sublet", "sublease", "occupancy", "arrears", "late fee", "rights", "obligation", "clause"
        }
        words = set(re.findall(r"\b\w+\b", query.lower()))
        return any(keyword in words for keyword in keywords)

    def _classify_input(self, query: str) -> str:
        try:
            query_lower = query.lower().strip()
            greetings = {"hello", "hi", "hey", "thanks", "good morning", "bye"}
            if query_lower.strip("!.?") in greetings:
                return "GREETING"

            strong_domain_terms = {"rights", "obligation", "clause", "agreement", "tenancy", "deposit"}
            if any(term in query_lower for term in strong_domain_terms):
                return "DOMAIN"

            # Feedback-like utterances should NOT go to DOMAIN
            feedback_terms = {"wrong", "not correct", "you did not answer", "incorrect"}
            if any(t in query_lower for t in feedback_terms):
                return "GENERAL"

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
            if "IDENTITY" in response:
                return "IDENTITY"
            return "DOMAIN"
        except Exception:
            return "DOMAIN"

    def _clean_rewrite(self, rewrite: str, original: str) -> str:
        clean = re.sub(r"^(Rewritten Question:|Rewritten:|Question:)", "", rewrite, flags=re.IGNORECASE).strip()
        clean = clean.strip('"').strip("'")
        if len(clean) > len(original) * 4:
            return original
        return clean if clean else original

    def _sanitize_answer_text(self, text: str) -> str:
        if not text:
            return text

        # Remove common junk headers / prompt echo
        bad_starts = (
            "important:",
            "question:",
            "sources:",
            "confidence:",
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

        # hard cap
        if len(cleaned) > 1800:
            cleaned = cleaned[:1800].rstrip() + "..."

        return cleaned

    def _needs_party_names(self, query: str) -> bool:
        q = query.lower()
        return any(k in q for k in ["tenant name", "tenants' name", "owner name", "landlord name", "party name", "parties"])

    def _context_mentions_party_names(self, context: str) -> bool:
        c = (context or "").lower()
        return any(k in c for k in ["tenant", "landlord", "party", "parties", "owner", "name:"])

    # -------------------------
    # Document text store (Option A)
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

    def _extract_text_from_file(self, path: str) -> str:
        """
        Best-effort extraction. Keeps it dependency-light:
        - PDF: try pypdf (if installed)
        - DOCX: try python-docx (if installed)
        - otherwise: treat as text
        """
        ext = os.path.splitext(path)[1].lower()

        # PDF
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

        # DOCX
        if ext == ".docx":
            try:
                import docx  # python-docx
                d = docx.Document(path)
                return "\n".join(p.text for p in d.paragraphs)
            except Exception:
                pass

        # Plaintext fallback
        try:
            with open(path, "rb") as f:
                raw = f.read()
            # try utf-8 then latin-1
            try:
                return raw.decode("utf-8", errors="ignore")
            except Exception:
                return raw.decode("latin-1", errors="ignore")
        except Exception:
            return ""

    def ingest_file(self, filename: str, content: bytes) -> str:
        """
        Saves bytes to a temp file, ingests via VectorService, stores extracted full text (Option A), then cleans up.
        """
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            print(f" [CRAG] Ingesting temp file: {tmp_path}")

            # 1) Vector ingest (your existing behavior)
            result = self.vector_service.ingest_document(tmp_path, file_name_override=filename)

            # 2) Extract + store full text for summarization
            full_text = self._extract_text_from_file(tmp_path)
            self._save_doc_text(filename, full_text)

            return result
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


    def summarize_document(self, file_name: str, focus: str | None = None, mode: str = "infographic") -> dict:
        """
        mode:
          - "summary": short structured summary
          - "infographic": returns infographic_json for UI cards (NotebookLM-ish)
        """
        doc_text = self._load_doc_text(file_name)
        if not doc_text.strip():
            return {
                "ok": False,
                "error": "No stored text for this document. Re-ingest the file first.",
                "file_name": file_name,
            }

        # Trim to keep generation fast (you can raise if your model is strong)
        doc_text = doc_text[:18000]

        focus = (focus or "").strip()
        focus_line = f"FOCUS TOPICS: {focus}\n" if focus else ""

        if mode == "summary":
            # Summary: GPT-4o-mini first, local Phi-3 fallback
            sum_sys = (
                "You are a document analyst. Summarize the provided document clearly and concisely "
                "for a real estate staff member. Use ONLY the document text. No outside knowledge."
            )
            sum_usr = (
                "Write a structured summary with these sections (plain prose, no markdown heading symbols):\n"
                "OVERVIEW: one sentence describing the document.\n"
                "KEY POINTS: up to 6 bullet points of the most important clauses.\n"
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
                        max_tokens=800,
                    )
                    text = resp.choices[0].message.content.strip()
                    return {"ok": True, "mode": "summary", "file_name": file_name, "text": text}
                except Exception as gpt_err:
                    print(f" [Summary] GPT failed ({gpt_err}), falling back to local LLM")
            # Fallback: local Phi-3
            fb_prompt = (
                "Summarize this document concisely. Output format:\n"
                "OVERVIEW: one sentence.\nKEY POINTS: up to 6 bullets.\nIMPORTANT TERMS: up to 6 terms.\n\n"
                f"{focus_line}DOCUMENT TEXT:\n{doc_text}"
            )
            text = self.llm.complete(fb_prompt).text.strip()
            return {"ok": True, "mode": "summary", "file_name": file_name, "text": text}


        # infographic mode: GPT-4o-mini first, Phi-3 fallback
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
                obj = json.loads(resp.choices[0].message.content.strip())
                return {"ok": True, "mode": "infographic", "file_name": file_name, "infographic": obj}
            except Exception as gpt_err:
                print(f" [Infographic] GPT failed ({gpt_err}), falling back to local LLM")

        # Fallback: local Phi-3
        fb_prompt = (
            "You turn a document into an infographic JSON outline."
            " Output MUST be valid JSON only (no markdown).\n"
            "{\"title\": string, \"one_liner\": string, "
            "\"cards\": [{\"heading\": string, \"bullets\": [string]}], "
            "\"key_terms\": [{\"term\": string, \"meaning\": string}], "
            "\"quick_faq\": [{\"q\": string, \"a\": string}]}\n\n"
            f"{focus_line}DOCUMENT TEXT:\n{doc_text}"
        )
        raw = self.llm.complete(fb_prompt).text.strip()
        try:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            obj = json.loads(m.group(0) if m else raw)
            return {"ok": True, "mode": "infographic", "file_name": file_name, "infographic": obj}
        except Exception:
            return {"ok": True, "mode": "infographic", "file_name": file_name, "infographic_raw": raw}

    def list_documents(self) -> list[str]:
        """
        Returns the filenames of all ingested documents.
        Used by GET /crag/documents
        """
        return self.vector_service.list_ingested_files()

    def delete_document(self, filename: str) -> bool:
        """
        Deletes a document from the vector store (and any related index entries).
        Used by DELETE /crag/documents/{filename}
        """
        return self.vector_service.delete_file(filename)
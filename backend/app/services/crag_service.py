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


class CRAGService:
    def __init__(self):
        print(f" [CRAG] Initializing with Model: {settings.LLM_MODEL}...")

        self.llm = Ollama(
            model=settings.LLM_MODEL,
            request_timeout=300.0,
            temperature=0.1,
            additional_kwargs={
                "num_ctx": 4096, 
                "num_predict": 1024,
                "stop": ["<|end|>", "<|user|>", "<|assistant|>", "---------------------"]
            }
        )
        LlamaSettings.llm = self.llm

        self.vector_service = VectorService()
        self.index = self.vector_service.get_index()
        self.reranker = SentenceTransformerRerank(
            model=settings.RERANKER_MODEL, top_n=5
        )

        # Chart service (external AI API)
        self.chart_service = ChartService()

        # --- PROMPTS ---

        # 1. CLASSIFY (Merged: CHART + USER PROVIDED CATEGORIES)
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

        self.rewrite_prompt = PromptTemplate(
            "Task: Rewrite the Follow-up Question to be standalone based on Context.\n"
            "Context: {history_str}\n"
            "Follow-up: {query_str}\n"
            "Rewritten Question:"
        )

        self.session_prompt = PromptTemplate(
            "User Input: {query_str}\n"
            "Extract the name they want to be called. If none, output NONE.\n"
            "Name:"
        )

        # D. MULTI-QUERY PROMPT
        self.multiquery_prompt = PromptTemplate(
            "You are an AI assistant. Your task is to generate 3 different search queries based on the user's follow-up question and conversation history.\n"
            "1. A direct rewrite of the question.\n"
            "2. A search for related keywords (e.g., 'fees', 'legal', 'clause').\n"
            "3. A hypothetical answer snippet (what the document might say).\n"
            "Context: {history_str}\n"
            "Follow-up: {query_str}\n"
            "Output ONLY the 3 queries, separated by a newline."
        )

        # --- TUNING 3.1: Strict Answer Generation Prompt ---
        # This prevents the LLM from using its own training data.
        self.qa_prompt_tmpl = (
            "<|user|>\n"
            "You are an expert Malaysian Real Estate Consultant.\n"
            "Answer the question using the context provided below.\n"
            "Extract and synthesize the relevant information from the context.\n"
            "If the exact answer isn't in the context but related information is present, provide what you found and note what's missing.\n"
            "NEVER make up information. NEVER use knowledge outside the context.\n"
            "Structure your response clearly:\n"
            "- Use ### Headers for main sections.\n"
            "- Use bullet points for lists, with a blank line between each item.\n"
            "- Use Markdown tables for comparisons.\n"
            "- Keep paragraphs short and readable.\n"
            "- Bold key terms only.\n"
            "Answer in the same language as the question.\n"
            "---------------------\n"
            "Context:\n"
            "{context_str}\n"
            "---------------------\n"
            "Question: {query_str}\n"
            "<|end|>\n"
            "<|assistant|>\n"
            "Answer:"
        )
        self.qa_prompt = PromptTemplate(self.qa_prompt_tmpl)

        self.qa_prompt = PromptTemplate(self.qa_prompt_tmpl)

    def generate_response(self, query: str, history: List[str] = [], user_context: Dict[str, Any] = {}) -> Dict[
        str, Any]:
        user_name = user_context.get("user_name", "")
        friendly_prefix = f"{user_name}, " if user_name else ""

        # STEP 1: CLASSIFY
        category = self._classify_input(query)
        if category == "GENERAL" and self._looks_domain_related(query):
            category = "DOMAIN"
        print(f" [CRAG] Intent: {category} | Query: '{query}'")

        result_template = {
            "answer": "",
            "sources": [],
            "intent": category,
            "session_updates": {},
            "infographic": "",
            "chart_data": None,
            "confidence": 1.0 
        }

        # STEP 2: HANDLE NON-RETRIEVAL
        if category == "GREETING":
            result_template[
                "answer"] = f"Hello {user_name}! I can help with tenancy agreements and property questions." if user_name else "Hello! I am your Real Estate Assistant."
            return result_template

        if category == "SESSION":
            try:
                extracted_name = self.llm.complete(self.session_prompt.format(query_str=query)).text.strip()
                extracted_name = re.sub(r"[^\w\s]", "", extracted_name)
                if extracted_name and "NONE" not in extracted_name and len(extracted_name) < 20:
                    result_template["answer"] = f"Nice to meet you, {extracted_name}."
                    result_template["session_updates"] = {"user_name": extracted_name}
                else:
                    result_template["answer"] = "Understood."
            except Exception as e:
                print(f" [CRAG] Session extraction error: {e}")
                result_template["answer"] = "Understood."
            return result_template

        if category == "GENERAL":
            # Allow LLM to answer general questions directly without RAG
            # This prevents "I only focus on..." blocks for simple questions
            try:
                response = self.llm.complete(query).text.strip()
                result_template["answer"] = response
            except:
                 result_template["answer"] = "I am a Real Estate Assistant. Please ask me about tenancy agreements."
            return result_template

        if category == "IDENTITY":
            result_template["answer"] = (
                "I am your expert Real Estate Consultant. I can help you with:\n"
                "- Reviewing Tenancy Agreements\n"
                "- Explaining Legal Clauses (Stamping, Termination)\n"
                "- Calculating Stamp Duty\n"
                "- Answering questions about Property Law\n\n"
                "Please upload a document or ask me a question to get started."
            )
            return result_template

        # STEP 3: PREPARE QUERY
        search_query = query

        # --- TUNING 3.4: Query Normalization ---
        # Fix common grammar mistakes to improve embedding recall
        search_query = self._normalize_query(search_query)

        if category == "DEPENDENT":
            if history:
                print(" [CRAG] Rewriting...")
                raw_rewrite = self._rewrite_query(query, history)
                search_query = self._clean_rewrite(raw_rewrite, query)
                print(f" [CRAG] Rewritten: '{search_query}'")
            else:
                result_template[
                    "answer"] = f"{friendly_prefix}could you please clarify which agreement you are referring to?"
                return result_template

        # STEP 4: EXECUTE RAG WITH SAFETY
        rag_result = self._run_rag_pipeline(search_query)

        # Corrective Retrieval (Simple Loop)
        if rag_result.get("low_confidence"):
            print(" [CRAG] Low confidence. Attempting corrective rewrite...")
            # Try to simplify or use keywords
            new_query = self._rewrite_query(search_query, history)
            if new_query != search_query:
                 print(f" [CRAG] Retrying with: {new_query}")
                 rag_result = self._run_rag_pipeline(new_query)

        # --- TUNING 3.2: Keep responses concise ---
        final_answer = rag_result["answer"]
        # --- TUNING 3.2: Keep responses succinct but allow detail ---
        final_answer = rag_result["answer"]
        if len(final_answer) > 6000:
            final_answer = f"{final_answer[:6000].rstrip()}..."

        if rag_result.get("low_confidence"):
            final_answer = (
                "I could not find an exact match, but here is the closest relevant information from the documents:\n"
                f"{final_answer}"
            )



        if self._looks_domain_related(query):
            if self.chart_service.enabled:
                chart_data = self.chart_service.extract_chart_data(final_answer, query)
            else:
                chart_data = self._try_extract_chart_data(final_answer, query)
            if chart_data:
                result_template["chart_data"] = chart_data

        result_template["answer"] = final_answer
        result_template["sources"] = rag_result["sources"]
        result_template["low_confidence"] = rag_result.get("low_confidence", False)
        result_template["confidence"] = rag_result.get("confidence_score", 1.0)

        # Pass debug info
        result_template["debug_nodes"] = rag_result.get("debug_nodes", [])

        return result_template

    def _try_extract_chart_data(self, context: str, query: str) -> Union[List[Dict], None]:
        """Specifically asks the LLM to format data for a chart if relevant."""
        if not any(word in query.lower() for word in ["graph", "chart", "visualize", "compare", "trend", "statistics", "data"]):
            return None
        
        prompt = (
            f"Context: {context}\n"
            f"Query: {query}\n"
            "Task: Extract numerical data for a chart.\n"
            "Constraint: Output ONLY a valid JSON list of objects with 'label' and 'value'.\n"
            "Example: [{\"label\": \"Rent\", \"value\": 2000}, {\"label\": \"Deposit\", \"value\": 500}]\n"
            "Do NOT write Python code. Do NOT explain. ONLY JSON."
        )
        try:
            response = self.llm.complete(prompt).text.strip()
            # Clean response to ensure it's only JSON
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                data = json.loads(match.group())
                if isinstance(data, list) and len(data) > 0 and 'label' in data[0] and 'value' in data[0]:
                    return data
        except:
            return None
        return None

    def _normalize_query(self, query: str) -> str:
        """Fixes common grammar issues for better retrieval"""
        q = query.lower()
        # Fix "what should included" -> "what should include"
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
            query_lower = query.lower()
            greetings = {'hello', 'hi', 'hey', 'thanks', 'good morning', 'bye'}
            if query_lower.strip().strip('!.?') in greetings: return "GREETING"

            # Force DOMAIN for strong keywords to prevent IDENTITY/GENERAL drift
            strong_domain_terms = {'rights', 'obligation', 'clause', 'agreement', 'tenancy', 'deposit'}
            if any(term in query_lower for term in strong_domain_terms):
                return "DOMAIN"

            prompt = self.classify_prompt.format(query_str=query)
            response = self.llm.complete(prompt).text.strip().upper()

            if "GREETING" in response: return "GREETING"
            if "SESSION" in response: return "SESSION"
            if "GENERAL" in response: return "GENERAL"
            if "DEPENDENT" in response: return "DEPENDENT"
            if "IDENTITY" in response: return "IDENTITY"
            return "DOMAIN"
        except:
            return "DOMAIN"

    def _run_rag_pipeline(self, search_query: str) -> dict:
        # 1. Retrieve (Top K = 20)
        retriever = VectorIndexRetriever(index=self.index, similarity_top_k=20)
        nodes = retriever.retrieve(search_query)

        print(f" [CRAG] Retrieved {len(nodes)} nodes")

        # 2. Rerank (Top N = 7) - Increased from 5
        if nodes:
            nodes = self.reranker.postprocess_nodes(nodes, query_str=search_query)

        # --- TUNING 3.3: Normalize Scores (Sigmoid) ---
        # Cross-Encoders return logits (can be negative). We normalize to 0-1.
        import math
        def sigmoid(x):
            return 1 / (1 + math.exp(-x))

        if not nodes:
            best_score = 0
            best_raw = -999
        else:
            best_raw = nodes[0].score if nodes[0].score is not None else -999
            best_score = sigmoid(best_raw)

        print(f" [CRAG] Best Raw Score: {best_raw:.2f} | Normalized: {best_score:.2f}")

        if nodes:
            print(f" [CRAG] Top 3 sources:")
            for i, node in enumerate(nodes[:3]):
                fname = node.metadata.get('file_name', 'Unknown')
                s_raw = node.score if node.score else -999
                s_norm = sigmoid(s_raw)
                print(f"   {i+1}. {fname} - Score: {s_norm:.3f}")

        # If the best score is below 0.15 (normalized), the retrieval failed.
        if not nodes or best_score < 0.15:
            print(" [CRAG] Very Low Confidence - No Results")
            return {
                "answer": (
                    "I searched the internal documents but couldn't find a close match. "
                    "Could you clarify the specific clause, property, or topic (e.g., deposit, "
                    "termination, repairs) so I can narrow it down?"
                ),
                "sources": [],
                "debug_nodes": [],
                "low_confidence": True
            }

        low_confidence = best_score < 0.5
        if low_confidence:
            print(f" [CRAG] Low Confidence: {best_score:.2f} (Raw: {best_raw:.2f})")

        # 3. Generate Answer (Strict)
        synthesizer = get_response_synthesizer(
            text_qa_template=self.qa_prompt,  # Apply STRICT prompt
            response_mode="compact"
        )
        response_obj = synthesizer.synthesize(search_query, nodes=nodes)

        # 4. Extract Sources
        source_list = []
        debug_nodes_data = []
        for node in response_obj.source_nodes:
            file_name = node.metadata.get("file_name", "Unknown")
            page_label = node.metadata.get("page_label", "N/A")
            # Normalize score for UI display
            raw_node_score = node.score if node.score is not None else -999
            norm_score = sigmoid(raw_node_score)
            score = f"{norm_score:.2f}" 
            text_preview = node.get_content()[:100]

            source_list.append(f"{file_name} (Page {page_label}) - Score: {score}")
            debug_nodes_data.append(f"[{score}] {file_name}: {text_preview}...")

        return {
            "answer": str(response_obj),
            "sources": source_list[:3],
            "debug_nodes": debug_nodes_data,
            "low_confidence": low_confidence,
            "confidence_score": best_score # RETURN THE CALCULATED SCORE
        }



    def _rewrite_query(self, query: str, history: List[str]) -> str:
        try:
            # Use last 5-7 turns for better context
            history_str = "\n".join(history[-7:])

            prompt = self.multiquery_prompt.format(history_str=history_str, query_str=query)
            response = self.llm.complete(prompt).text.strip()
            
            lines = response.strip().split('\n')
            # Pick the first non-empty rewrite
            for line in lines:
                clean = line.strip()
                if clean and len(clean) > 5:
                    print(f" [CRAG] Using rewrite: {clean}")
                    return clean
            return query  # Fallback to original
        except:
            return query

    def _clean_rewrite(self, rewrite: str, original: str) -> str:
        clean = re.sub(r'^(Rewritten Question:|Rewritten:|Question:)', '', rewrite, flags=re.IGNORECASE).strip()
        clean = clean.strip('"').strip("'")
        if len(clean) > len(original) * 4 or "apologize" in clean.lower(): return original
        return clean if clean else original

    # --- FILE INGESTION ---

    def ingest_file(self, filename: str, content: bytes) -> str:
        """
        Saves bytes to a temp file, ingests via VectorService, then cleans up.
        """
        # Create a temp file with the correct extension
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            print(f" [CRAG] Ingesting temp file: {tmp_path}")
            # Pass original filename to override the temp path in metadata
            result = self.vector_service.ingest_document(tmp_path, file_name_override=filename)
            return result
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def list_documents(self) -> List[str]:
        return self.vector_service.list_ingested_files()

    def delete_document(self, filename: str) -> bool:
        return self.vector_service.delete_file(filename)

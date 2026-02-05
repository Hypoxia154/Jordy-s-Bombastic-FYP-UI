from typing import List, Dict, Any
import json
import re
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings as LlamaSettings, get_response_synthesizer, PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from app.core.config import settings
from app.services.vector_store import VectorService


class CRAGService:
    def __init__(self):
        print(f" [CRAG] Initializing with Model: {settings.LLM_MODEL}...")

        # 1. Setup Phi-3 (SLM)
        self.llm = Ollama(
            model=settings.LLM_MODEL,
            request_timeout=300.0,
            additional_kwargs={"num_ctx": 2048, "num_predict": 512}
        )
        LlamaSettings.llm = self.llm

        # 2. Setup Vector Store & Reranker
        self.vector_service = VectorService()
        self.index = self.vector_service.get_index()
        self.reranker = SentenceTransformerRerank(
            model=settings.RERANKER_MODEL, top_n=5
        )

        # --- PROMPTS ---

        # A. INTENT CLASSIFIER (The Gatekeeper)
        self.classify_prompt = PromptTemplate(
            "Analyze the User Query. Classify it into exactly one category:\n"
            "1. GREETING: (Hello, Hi, Thanks, Bye)\n"
            "2. GENERAL: (Weather, Date, Time, Jokes, General Knowledge not related to Real Estate)\n"
            "3. DOMAIN: (Real Estate, Tenancy, Contracts, Rent, Property, Fees)\n"
            "4. DEPENDENT: (Ambiguous questions referring to previous context, e.g., 'Who pays it?', 'How much?')\n\n"
            "Query: {query_str}\n"
            "Answer ONLY with the Category Name (GREETING, GENERAL, DOMAIN, DEPENDENT)."
        )

        # B. REWRITE PROMPT
        self.rewrite_prompt = PromptTemplate(
            "Task: Rewrite the Follow-up Question to be standalone based on the Context.\n"
            "Context: {history_str}\n"
            "Follow-up: {query_str}\n"
            "Rewritten Question:"
        )

        # C. CHART EXTRACT PROMPT
        self.chart_prompt = PromptTemplate(
            "You are a Data Analyst. Your goal is to visualize the answer.\n"
            "Extract data from the Context below to answer the Query.\n"
            "Return the output as VALID JSON ONLY. Do not add any text before or after.\n"
            "Format:\n"
            "{{\n"
            "  \"title\": \"Chart Title\",\n"
            "  \"type\": \"bar\",  // or line, pie\n"
            "  \"data\": {{\n"
            "    \"labels\": [\"Label1\", \"Label2\"],\n"
            "    \"datasets\": [\n"
            "      {{ \"label\": \"Dataset Name\", \"data\": [10, 20] }}\n"
            "    ]\n"
            "  }},\n"
            "  \"summary\": \"Brief explanation of the chart.\"\n"
            "}}\n\n"
            "Context: {context_str}\n"
            "Query: {query_str}\n"
            "JSON Output:"
        )


    def generate_response(self, query: str, history: List[str] = []) -> str:
        """
        Pipeline: Classify -> Gatekeep -> Route -> Execute
        Returns a Dictionary: {'answer': str, 'sources': List[str]}
        """
        # STEP 1: CLASSIFY INTENT
        category = self._classify_input(query)
        if category == "CHART":
            search_query = query
            # We skip rewriting for explicit chart requests usually, or could rewrite if ambiguous
            print(f" [CRAG] Chart Request detected: '{query}'")
            return self._run_chart_pipeline(search_query)

        # STEP 2: HANDLE NON-RETRIEVAL CATEGORIES
        if category == "GREETING":
            return {"answer": "Hello! I am your Real Estate AI Assistant...", "sources": [], "chart_data": None}

        if category == "GENERAL":
            return {"answer": "I am designed specifically for Real Estate queries...", "sources": [], "chart_data": None}

        # STEP 3: HANDLE RETRIEVAL CATEGORIES (DOMAIN & DEPENDENT)
        search_query = query

        # Only rewrite if it is DEPENDENT and we actually have history
        if category == "DEPENDENT":
            if history:
                print(" [CRAG] Context dependency detected. Rewriting...")
                raw_rewrite = self._rewrite_query(query, history)
                search_query = self._clean_rewrite(raw_rewrite, query)
                print(f" [CRAG] Rewritten Query: '{search_query}'")
            else:
                # If dependent but no history, ask for clarification
                return {
                    "answer": "Could you please clarify what specific property or agreement you are asking about?",
                    "sources": [],
                    "chart_data": None
                }

        # STEP 4: EXECUTE RAG
        return self._run_rag_pipeline(search_query)

    def _classify_input(self, query: str) -> str:
        """Determines Intent using Phi-3"""
        try:
            q_lower = query.lower()
            
            # Fast keyword check for greetings
            greetings = {'hello', 'hi', 'hey', 'good morning', 'thanks'}
            if q_lower.strip().strip('!.?') in greetings:
                return "GREETING"

            # Fast keyword check for Chart
            chart_terms = {'chart', 'graph', 'plot', 'visualize', 'trend'}
            if any(term in q_lower for term in chart_terms):
                return "CHART"

            # Fast keyword check for Domain (Force DOMAIN for these terms)
            domain_terms = {'rent', 'landlord', 'tenant', 'deposit', 'agreement', 'property', 'house', 'room', 'pay', 'contract'}
            if any(term in q_lower for term in domain_terms):
                return "DOMAIN"

            prompt = self.classify_prompt.format(query_str=query)
            response = self.llm.complete(prompt).text.strip().upper()

            if "GREETING" in response: return "GREETING"
            if "GENERAL" in response: return "GENERAL"
            if "DEPENDENT" in response: return "DEPENDENT"
            return "DOMAIN"  # Default to Domain if unsure
        except:
            return "DOMAIN"

    def _run_rag_pipeline(self, search_query: str) -> dict:
        # 1. Retrieve
        retriever = VectorIndexRetriever(index=self.index, similarity_top_k=15)
        nodes = retriever.retrieve(search_query)

        # 2. Rerank
        if nodes:
            nodes = self.reranker.postprocess_nodes(nodes, query_str=search_query)

        # 3. Check emptiness
        # If the best match has a score lower than 0.5, it's probably junk.
        if not nodes or (nodes[0].score is not None and nodes[0].score < 0.1):  # Threshold varies by model
            print(f" [CRAG] Low confidence score: {nodes[0].score if nodes else 0}")
            return {
                "answer": "I found some documents, but they don't seem closely related to your question. Could you be more specific?",
                "sources": []
            }
        # 4. Generate Answer
        synthesizer = get_response_synthesizer(response_mode="compact")
        response_obj = synthesizer.synthesize(search_query, nodes=nodes)

        # 5. Extract Sources (NEW)
        source_list = []
        for node in response_obj.source_nodes:
            # LlamaIndex stores metadata in node.metadata
            file_name = node.metadata.get("file_name", "Unknown File")
            page_label = node.metadata.get("page_label", "N/A")
            score = f"{node.score:.2f}" if node.score else "N/A"
            source_list.append(f"{file_name} (Page {page_label}) - Score: {score}")


        return {
            "answer": str(response_obj),
            "sources": source_list[:3],  # Return top 3 unique sources
            "chart_data": None
        }

    def _run_chart_pipeline(self, search_query: str) -> dict:
        # 1. Retrieve
        retriever = VectorIndexRetriever(index=self.index, similarity_top_k=10)
        nodes = retriever.retrieve(search_query)
        
        if not nodes:
             return {"answer": "I couldn't find enough data to make a chart.", "sources": [], "chart_data": None}

        # 2. Extract Data (RAG directly to JSON)
        context_str = "\n\n".join([n.get_content() for n in nodes])
        prompt = self.chart_prompt.format(context_str=context_str, query_str=search_query)
        
        try:
            json_response = self.llm.complete(prompt).text.strip()
            # Robust JSON extraction
            json_match = re.search(r'\{.*\}', json_response, re.DOTALL)
            if json_match:
                json_response = json_match.group(0)
            else:
                # Fallback: clean potential markdown wrappers if regex missed
                if "```json" in json_response:
                    json_response = json_response.split("```json")[1].split("```")[0].strip()
                elif "```" in json_response:
                    json_response = json_response.split("```")[1].split("```")[0].strip()
                
            chart_data = json.loads(json_response)
            
            # Extract Sources
            source_list = []
            for node in nodes[:3]:
                 file_name = node.metadata.get("file_name", "Unknown File")
                 source_list.append(f"{file_name}")

            return {
                "answer": chart_data.get("summary", "Here is the visualization you requested."),
                "sources": source_list,
                "chart_data": chart_data
            }
        except Exception as e:
            print(f" [CRAG] Chart Generation Failed: {e}")
            return {
                "answer": "I tried to generate a chart but couldn't parse the data. Here is the raw info instead.",
                "sources": [],
                "chart_data": None
            }

    def _rewrite_query(self, query: str, history: List[str]) -> str:
        try:
            # Use last 2 turns
            history_str = "\n".join(history[-2:])
            prompt = self.rewrite_prompt.format(history_str=history_str, query_str=query)
            return self.llm.complete(prompt).text.strip()
        except:
            return query

    def _clean_rewrite(self, rewrite: str, original: str) -> str:
        clean = re.sub(r'^(Rewritten Question:|Rewritten:|Question:)', '', rewrite, flags=re.IGNORECASE).strip()
        clean = clean.strip('"').strip("'")
        # Safety valve: if rewrite is huge or apologetic, revert
        if len(clean) > len(original) * 4 or "apologize" in clean.lower():
            return original
        return clean if clean else original

    def ingest_file(self, filename: str, content: bytes) -> str:
        """
        Saves bytes to a temp file, ingests via VectorService, then cleans up.
        """
        import tempfile
        import os

        # Create a temp file with the correct extension
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            print(f" [CRAG] Ingesting temp file: {tmp_path}")
            result = self.vector_service.ingest_document(tmp_path)
            return result
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


import time
from typing import Generator
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings, get_response_synthesizer, PromptTemplate
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from app.services import vector_store  # Import the file we just created


class CRAGService:
    def __init__(self):
        print(" [Backend] Initializing TinyLlama & Reranker...")
        self.collection_name = "crag_llamaindex"

        # 1. SETUP LLM (Ollama)
        try:
            self.llm = Ollama(
                model="tinyllama",
                request_timeout=360.0,
                # Stop tokens prevent infinite roleplaying
                additional_kwargs={"stop": ["User:", "\nUser:", "Assistant:", "\nAssistant:"]}
            )
            Settings.llm = self.llm
        except Exception as e:
            print(f"❌ Error initializing Ollama: {e}")

        # 2. SETUP RERANKER
        try:
            self.reranker = SentenceTransformerRerank(
                model="cross-encoder/ms-marco-MiniLM-L-6-v2",
                top_n=3
            )
        except Exception as e:
            print(f"❌ Error initializing Reranker: {e}")
            self.reranker = None

        # 3. PROMPTS
        self.rewrite_prompt = PromptTemplate(
            "User: {query_str}\n"
            "History: {history_str}\n"
            "Instruction: Rewrite the User's question to include details from History. Output ONLY the rewrite.\n"
            "Rewrite:"
        )

        self.general_chat_prompt = PromptTemplate(
            "Conversation History:\n{history_str}\n\n"
            "User: {query_str}\n"
            "Assistant:"
        )

    def answer_stream(self, question: str, history: list = None) -> Generator[str, None, None]:
        """
        Main RAG Pipeline - Yields strings for StreamingResponse
        """
        print(f" [Service] Question: '{question}'")

        # 1. REWRITE QUERY
        search_query = question
        if history and len(history) > 0:
            search_query = self._contextualize(question, history)

        # 2. RETRIEVE FROM QDRANT
        nodes = []
        try:
            index = vector_store.get_index(self.collection_name)
            if index:
                retriever = VectorIndexRetriever(index=index, similarity_top_k=10)
                raw_nodes = retriever.retrieve(search_query)

                if raw_nodes and self.reranker:
                    nodes = self.reranker.postprocess_nodes(raw_nodes, query_str=search_query)
                    nodes = [n for n in nodes if n.score > 0.0]  # Filter bad matches
        except Exception as e:
            print(f"   -> ⚠️ Retrieval Error: {e}")

        # 3. GENERATE (Stream)

        # Case A: RAG (Docs Found)
        if nodes:
            print(f"   -> ✅ Found {len(nodes)} docs. Streaming RAG...")

            # Create a simple Context Prompt
            qa_prompt = PromptTemplate(
                "Context:\n{context_str}\n\n"
                "Question: {query_str}\n"
                "Answer:"
            )

            synthesizer = get_response_synthesizer(
                response_mode="tree_summarize",
                text_qa_template=qa_prompt,
                streaming=True
            )
            response = synthesizer.synthesize(search_query, nodes=nodes)

            # Yield response tokens
            for token in response.response_gen:
                yield token

        # Case B: General Chat (No Docs)
        else:
            print("   -> 0 docs found. Streaming Chat Mode...")

            clean_history = "\n".join(history[-6:]) if history else ""
            prompt = self.general_chat_prompt.format(history_str=clean_history, query_str=question)

            stream_gen = self.llm.stream_complete(prompt)

            for response_chunk in stream_gen:
                yield response_chunk.delta

    def _contextualize(self, query, history):
        """Rewrites query based on history"""
        try:
            history_str = "\n".join(history[-2:])
            response = self.llm.complete(
                self.rewrite_prompt.format(history_str=history_str, query_str=query)
            )
            clean = str(response).strip().strip('"').strip("'")
            return clean if len(clean) < len(query) + 50 else query
        except:
            return query
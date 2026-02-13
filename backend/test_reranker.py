from sentence_transformers import CrossEncoder

def test_reranker():
    query = "ok can you elaborate my full tenant rights?"
    document_text = """
    7. Right to terminate the rental agreement by giving written notice of at least two months in advance (7). This will refund your deposit if done correctly, but remember not using it for monthly rent during this period.
    8. Responsibility for repairing any damage caused due to negligence or hired help (16). You must ensure the Said House is returned in good condition at the end of the lease term unless otherwise agreed upon with written consent from your Landlord.
    11. Right for your landlord's representative or employees to enter Said House anytime necessary, provided they give prior notice.
    """
    
    print("\n--- Testing Reranker Models ---")
    print(f"Query: {query}")

    models = [
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "BAAI/bge-reranker-base"
    ]

    import math
    def sigmoid(x): return 1 / (1 + math.exp(-x))

    for model_name in models:
        try:
            print(f"\nLoading model: {model_name}...")
            model = CrossEncoder(model_name)
            
            score = model.predict([query, document_text])
            print(f"Raw Score: {score}")
            print(f"Normalized Score: {sigmoid(score)}")
            
        except Exception as e:
            print(f"Failed to load/run {model_name}: {e}")

if __name__ == "__main__":
    test_reranker()

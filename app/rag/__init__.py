"""RAG pipeline: embedder, query expansion (rewrite + HyDE), hybrid retriever,
cross-encoder reranker, and the orchestrator that ties them together with
self-RAG / corrective-RAG grading. Fully local (Ollama + a local cross-encoder).
"""

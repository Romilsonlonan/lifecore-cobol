"""
LifeCore AI Layer — RAG package

Exporta os símbolos públicos utilizados pelo ai_router e pelos testes.
"""

from app.ai.rag.engine import (
    Document,
    Embedder,
    Indexer,
    RAGEngine,
    RAGResponse,
    RetrievedChunk,
    VectorStore,
    chunk_text,
    get_rag_engine,
)
from app.ai.rag.transforms import (
    TRANSFORM_REGISTRY,
    AbendTransform,
    BaseTransform,
    CobolTransform,
    CopybookTransform,
    JclTransform,
    MarkdownTransform,
    NullTransform,
    PythonTransform,
    SqlTransform,
    get_transform,
)

__all__ = [
    # engine
    "RAGEngine",
    "RAGResponse",
    "Embedder",
    "VectorStore",
    "Indexer",
    "Document",
    "RetrievedChunk",
    "get_rag_engine",
    "chunk_text",
    # transforms
    "get_transform",
    "TRANSFORM_REGISTRY",
    "BaseTransform",
    "CobolTransform",
    "CopybookTransform",
    "JclTransform",
    "SqlTransform",
    "MarkdownTransform",
    "AbendTransform",
    "PythonTransform",
    "NullTransform",
]

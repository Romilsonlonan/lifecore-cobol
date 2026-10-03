"""
LifeCore AI Layer — RAG Engine
Indexa documentos técnicos (RUNBOOK, logs de abend, copybooks, JCL)
e responde perguntas usando Retrieval-Augmented Generation.

Arquitetura:
  Documentos → Chunking → Embeddings (sentence-transformers) → ChromaDB
  Pergunta   → Embedding → Busca semântica → Contexto → LLM → Resposta

Uso local (sem API paga):
  - Embeddings: all-MiniLM-L6-v2  (384 dims, 80MB, roda em CPU)
  - LLM:        qualquer modelo via openai-compatible API (ollama, lm-studio)
  - VectorDB:   ChromaDB (embedded, sem servidor)
"""
from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
EMBED_MODEL   = os.getenv("RAG_EMBED_MODEL",   "all-MiniLM-L6-v2")
CHROMA_PATH   = os.getenv("RAG_CHROMA_PATH",   "/tmp/lifecore_chroma")
COLLECTION    = os.getenv("RAG_COLLECTION",     "lifecore_docs")
LLM_BASE_URL  = os.getenv("LLM_BASE_URL",       "http://localhost:11434/v1")
LLM_API_KEY   = os.getenv("LLM_API_KEY",        "ollama")
LLM_MODEL     = os.getenv("LLM_MODEL",          "llama3.2")
CHUNK_SIZE    = int(os.getenv("RAG_CHUNK_SIZE",  "500"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "80"))
TOP_K         = int(os.getenv("RAG_TOP_K",       "5"))


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Document:
    """Unidade de texto indexada no vector store."""
    doc_id:   str
    text:     str
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    doc_id:    str
    text:      str
    score:     float
    metadata:  dict = field(default_factory=dict)


@dataclass
class RAGResponse:
    answer:         str
    sources:        list[RetrievedChunk]
    query:          str
    model_used:     str
    context_tokens: int


# ── Chunker ───────────────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Divide texto em chunks de tamanho fixo com sobreposição.
    Tenta preservar quebras de parágrafo/seção quando possível.
    """
    # Divide por seções markdown (## / ###) primeiro
    sections = re.split(r"\n(?=#{1,3} )", text)
    chunks: list[str] = []

    for section in sections:
        words = section.split()
        if len(words) <= size:
            if words:
                chunks.append(section.strip())
            continue
        # Chunk por palavras com overlap
        for i in range(0, len(words), size - overlap):
            chunk = " ".join(words[i : i + size])
            if chunk.strip():
                chunks.append(chunk.strip())

    return chunks


# ── Embedder ──────────────────────────────────────────────────────────────────

class Embedder:
    """Wrapper sentence-transformers — roda 100% local em CPU."""

    def __init__(self, model_name: str = EMBED_MODEL):
        from sentence_transformers import SentenceTransformer
        logger.info("Carregando modelo de embedding: %s", model_name)
        self._model = SentenceTransformer(model_name)
        self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return vecs.tolist()

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


# ── Vector Store (ChromaDB) ───────────────────────────────────────────────────

class VectorStore:
    """ChromaDB persistente — embedded, sem servidor."""

    def __init__(self, path: str = CHROMA_PATH, collection: str = COLLECTION):
        import chromadb
        self._client = chromadb.PersistentClient(path=path)
        self._col    = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB → %s | coleção: %s | docs: %d",
                    path, collection, self._col.count())

    def upsert(self, docs: list[Document], embeddings: list[list[float]]) -> None:
        self._col.upsert(
            ids=[d.doc_id for d in docs],
            documents=[d.text for d in docs],
            embeddings=embeddings,
            metadatas=[d.metadata for d in docs],
        )
        logger.info("Upsert de %d chunks na coleção.", len(docs))

    def query(self, embedding: list[float], top_k: int = TOP_K) -> list[RetrievedChunk]:
        results = self._col.query(
            query_embeddings=[embedding],
            n_results=min(top_k, max(1, self._col.count())),
            include=["documents", "distances", "metadatas"],
        )
        chunks = []
        for i, doc_id in enumerate(results["ids"][0]):
            chunks.append(RetrievedChunk(
                doc_id=doc_id,
                text=results["documents"][0][i],
                score=1 - results["distances"][0][i],  # cosine → similaridade
                metadata=results["metadatas"][0][i] or {},
            ))
        return chunks

    def count(self) -> int:
        return self._col.count()

    def reset(self) -> None:
        self._col.delete(where={"source": {"$ne": "__never__"}})
        logger.warning("Coleção resetada.")


# ── Indexer ───────────────────────────────────────────────────────────────────

class Indexer:
    """Lê arquivos do projeto e os indexa no VectorStore."""

    # Extensões e prefixos reconhecidos
    FILE_TYPES = {
        ".md":  "markdown",
        ".cbl": "cobol",
        ".cpy": "copybook",
        ".jcl": "jcl",
        ".sql": "sql",
        ".py":  "python",
    }

    def __init__(self, embedder: Embedder, store: VectorStore):
        self._embedder = embedder
        self._store    = store

    def index_file(self, path: Path, source_tag: str | None = None) -> int:
        """Indexa um único arquivo. Retorna número de chunks indexados."""
        suffix = path.suffix.lower()
        if suffix not in self.FILE_TYPES:
            logger.debug("Extensão não suportada: %s", path)
            return 0

        text = path.read_text(encoding="utf-8", errors="replace")
        chunks = chunk_text(text)
        if not chunks:
            return 0

        docs = [
            Document(
                doc_id   = f"{path.stem}::{i}",
                text     = chunk,
                metadata = {
                    "source":    source_tag or path.name,
                    "file_type": self.FILE_TYPES[suffix],
                    "file_path": str(path),
                    "chunk_idx": i,
                },
            )
            for i, chunk in enumerate(chunks)
        ]

        embeddings = self._embedder.embed([d.text for d in docs])
        self._store.upsert(docs, embeddings)
        return len(docs)

    def index_directory(self, root: Path, recursive: bool = True) -> dict[str, int]:
        """Indexa todos os arquivos reconhecidos em um diretório."""
        pattern = "**/*" if recursive else "*"
        totals: dict[str, int] = {}
        for path in root.glob(pattern):
            if path.is_file():
                n = self.index_file(path, source_tag=path.relative_to(root).as_posix())
                if n:
                    totals[str(path)] = n
        total_chunks = sum(totals.values())
        logger.info("Indexação concluída: %d arquivos, %d chunks.", len(totals), total_chunks)
        return totals

    def index_text(self, text: str, doc_id: str, metadata: dict | None = None) -> int:
        """Indexa texto avulso (ex: saída de log, dump de abend)."""
        chunks = chunk_text(text)
        docs = [
            Document(
                doc_id   = f"{doc_id}::{i}",
                text     = chunk,
                metadata = {**(metadata or {}), "source": doc_id, "chunk_idx": i},
            )
            for i, chunk in enumerate(chunks)
        ]
        embeddings = self._embedder.embed([d.text for d in docs])
        self._store.upsert(docs, embeddings)
        return len(docs)


# ── RAG Engine ────────────────────────────────────────────────────────────────

class RAGEngine:
    """
    Motor RAG principal.

    Fluxo:
      1. Busca semântica (retrieve)
      2. Monta prompt com contexto (augment)
      3. Chama LLM (generate)

    Compatível com qualquer backend que implemente a API OpenAI
    (Ollama, LM Studio, OpenAI, Azure, Groq, etc.)
    """

    SYSTEM_PROMPT = """Você é o assistente técnico do LifeCore-Mainframe,
especializado em diagnóstico de falhas em sistemas COBOL/z/OS, análise de
abends, JCL, DB2 e seguros de vida em grupo (VGC/GLB).

Responda sempre em português (BR), com precisão técnica.
Se não souber a resposta, diga "Não encontrei informação suficiente nos
documentos indexados." — nunca invente código ou configurações.

Use os trechos de documentação fornecidos como base principal da resposta.
Cite a fonte (nome do arquivo) quando relevante."""

    def __init__(
        self,
        embedder: Embedder,
        store:    VectorStore,
        model:    str = LLM_MODEL,
    ):
        self._embedder = embedder
        self._store    = store
        self._model    = model
        self._client   = self._build_client()

    def _build_client(self):
        try:
            from openai import OpenAI
            return OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
        except ImportError:
            logger.warning("openai não instalado — geração desabilitada.")
            return None

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[RetrievedChunk]:
        """Busca semântica — retorna os top_k chunks mais relevantes."""
        embedding = self._embedder.embed_one(query)
        return self._store.query(embedding, top_k=top_k)

    def generate(self, query: str, top_k: int = TOP_K) -> RAGResponse:
        """Recupera contexto e gera resposta com o LLM."""
        chunks = self.retrieve(query, top_k=top_k)

        if not chunks:
            return RAGResponse(
                answer="Nenhum documento indexado encontrado. Execute a indexação primeiro.",
                sources=[],
                query=query,
                model_used=self._model,
                context_tokens=0,
            )

        # Monta contexto com as fontes
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            src = chunk.metadata.get("source", "?")
            context_parts.append(f"[{i}] Fonte: {src}\n{chunk.text}")
        context = "\n\n---\n\n".join(context_parts)

        user_message = (
            f"Documentação de referência:\n\n{context}\n\n"
            f"---\n\nPergunta: {query}"
        )
        context_tokens = len(context.split())

        if self._client is None:
            # Modo sem LLM — retorna só o contexto recuperado
            return RAGResponse(
                answer=f"[Modo sem LLM] Contexto recuperado:\n\n{context}",
                sources=chunks,
                query=query,
                model_used="none",
                context_tokens=context_tokens,
            )

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system",  "content": self.SYSTEM_PROMPT},
                    {"role": "user",    "content": user_message},
                ],
                temperature=0.1,
                max_tokens=1024,
            )
            answer = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Erro na chamada LLM: %s", e)
            answer = f"Erro ao chamar LLM ({type(e).__name__}). Contexto recuperado:\n\n{context}"

        return RAGResponse(
            answer=answer,
            sources=chunks,
            query=query,
            model_used=self._model,
            context_tokens=context_tokens,
        )


# ── Singleton factory ─────────────────────────────────────────────────────────
_engine: RAGEngine | None = None

def get_rag_engine(force_new: bool = False) -> RAGEngine:
    """Retorna a instância singleton do RAGEngine (lazy init)."""
    global _engine
    if _engine is None or force_new:
        embedder = Embedder()
        store    = VectorStore()
        _engine  = RAGEngine(embedder, store)
    return _engine

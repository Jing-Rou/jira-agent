"""Persistent, multi-PDF hybrid RAG knowledge base for the Jira agent."""

from __future__ import annotations

import hashlib
from hmac import digest
import json
import os
from pathlib import Path
from threading import Lock
from urllib import response
from urllib.parse import unquote, urlparse

import chromadb
import requests
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.readers.file import PyMuPDFReader
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core import PromptTemplate
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.core.indices.query.query_transform.base import HyDEQueryTransform
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"

class KnowledgeBaseNotInitialized(RuntimeError):
    """Raised when retrieval is attempted before a PDF is loaded."""


class PDFKnowledgeBase:
    """Load PDFs and expose persistent hybrid vector/BM25 retrieval."""

    def __init__(
        self,
        embed_model: str,
        llm_model: str,
        RAG_OLLAMA_URL: str,
        chunk_size: int,
        chunk_overlap: int,
        storage_dir: str | Path | None = None,
    ) -> None:
        api_key = os.getenv("OLLAMA_API_KEY")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        self.embed_model = HuggingFaceEmbedding(model_name=embed_model)

        # self.embed_model = OllamaEmbedding(
        #     model_name=embed_model,
        #     base_url=RAG_OLLAMA_URL,
        #     client_kwargs={"headers": headers} if headers else None,
        # )
        self.llm = Ollama(
            model=llm_model,
            base_url=RAG_OLLAMA_URL,
            temperature=0,
            request_timeout=120.0,
            headers=headers or None,
        )
        self.splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.hyde = HyDEQueryTransform(llm=self.llm, include_original=True)
        self.retriever = None
        self.storage_dir = Path(storage_dir) if storage_dir else Path("kb_storage")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.response_synthesizer = None
        self.source_name = ""

        # Shared paths — one index for ALL documents, not one per PDF.
        self.chroma_dir = self.storage_dir / "chroma"
        self.bm25_dir = self.storage_dir / "bm25"
        self.registry_path = self.storage_dir / "registry.json"  # replaces active.json + per-doc manifest.json
        self.nodes_path = self.storage_dir / "nodes.jsonl" 
        
        self.loaded_from_cache = False
        self.node_count = 0
        self._loaded_digests: set[str] = set()

    def _registry(self) -> list[dict]:
        if self.registry_path.is_file():
            return json.loads(self.registry_path.read_text(encoding="utf-8"))
        return []

    def load(self, source: str | Path) -> int:
        """Build a PDF index once, or restore its persisted indexes on restart."""
        pdf_path = self._resolve_pdf(source)
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        self.source_name = pdf_path.name

        docs = self._registry()
        if any(d["digest"] == digest for d in docs):
            self.node_count = sum(d["node_count"] for d in docs)
            self.load_active()
            return self.node_count

        # read pdf file
        documents = PyMuPDFReader().load(file_path=str(pdf_path))
        # Split documents into chunks
        nodes = self.splitter.get_nodes_from_documents(documents)

        if not nodes:
                raise ValueError(f"No readable text was extracted from {pdf_path.name}")
        for node in nodes:
            node.metadata["source_name"] = pdf_path.name

        collection_name = "pdf_chunks"
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=str(self.chroma_dir))
        collection = chroma_client.get_or_create_collection(name=collection_name)
        
        # embed and store the embeddings in a Chroma vector store with vector index
        vector_store = ChromaVectorStore(chroma_collection=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        VectorStoreIndex(nodes, storage_context=storage_context, embed_model=self.embed_model)

        # NEW — append this document's raw chunks so BM25 can be rebuilt laters
        # from the full combined set (old docs + this one).
        with self.nodes_path.open("a", encoding="utf-8") as f:
            for node in nodes:
                f.write(json.dumps({"text": node.get_content(), "metadata": node.metadata}) + "\n")

        docs.append({"digest": digest, "source_name": pdf_path.name, "node_count": len(nodes)})
        self.registry_path.write_text(json.dumps(docs), encoding="utf-8")

        self._rebuild_bm25()
        self.load_active()
        return self.node_count

    def _rebuild_bm25(self) -> None:
        """NEW — BM25 has no incremental-add API, so every new document means
        re-reading all previously stored chunks and rebuilding from scratch."""
        all_nodes = []
        with self.nodes_path.open("r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                all_nodes.append(TextNode(text=row["text"], metadata=row["metadata"]))
        self.bm25_dir.mkdir(parents=True, exist_ok=True)
        BM25Retriever.from_defaults(nodes=all_nodes, similarity_top_k=6).persist(str(self.bm25_dir))


    def load_active(self) -> int:
        """Restore the active persisted index without requiring the PDF again."""
        docs = self._registry()
        if not docs:
            raise KnowledgeBaseNotInitialized("No documents indexed yet. Upload a PDF first.")

        client = chromadb.PersistentClient(path=str(self.chroma_dir))
        collection = client.get_or_create_collection("pdf_chunks")
        if collection.count() == 0:
            raise KnowledgeBaseNotInitialized("The persisted vector index is empty. Upload a PDF again.")

        vector_store = ChromaVectorStore(chroma_collection=collection)
        index = VectorStoreIndex.from_vector_store(vector_store, embed_model=self.embed_model)
        vector_retriever = index.as_retriever(similarity_top_k=8)

        # NEW — restore BM25 alongside the vector retriever
        bm25_retriever = BM25Retriever.from_persist_dir(str(self.bm25_dir))
        bm25_retriever.similarity_top_k = 8

        self.retriever = QueryFusionRetriever(
            [vector_retriever, bm25_retriever],
            llm=self.llm,
            similarity_top_k=5,
            num_queries=1,
            mode="reciprocal_rerank",
            use_async=False,
            verbose=False,
        )

        qa_prompt_tmpl = PromptTemplate(
            "You are the document-memory layer for a Jira support agent.\n"
            "Use only the supplied context. Never use outside knowledge and "
            "never invent live Jira values.\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "If the context fully answers the query, give a concise grounded answer.\n"
            "If it does not fully answer the query, or the query asks for current "
            "Jira issue data or an action the documents cannot prove, output ONLY "
            f"the exact text: {INSUFFICIENT_CONTEXT}\n"
            "Do not explain why, do not offer to help with something else, do not "
            "add any other words — output that exact string and nothing else.\n\n"
            "Example — context about table design, query about geography:\n"
            f"Answer: {INSUFFICIENT_CONTEXT}\n\n"
            "Query: {query_str}\n"
            "Answe  r: "
        )

        self.response_synthesizer = get_response_synthesizer(
            llm=self.llm,
            text_qa_template=qa_prompt_tmpl,
        )
        
        Settings.embed_model = self.embed_model
        Settings.llm = self.llm

        self.node_count = sum(d["node_count"] for d in docs)
        self.loaded_from_cache = True
        return self.node_count

    def search(self, query: str) -> list[dict]:
        """Retrieve relevant PDF chunks and return graph-friendly dictionaries."""
        if self.retriever is None:
            raise KnowledgeBaseNotInitialized("Load a PDF before searching the knowledge base")


        query_bundle = self.hyde(query)

        # retrieve relevant PDF chunks for the query
        results = self.retriever.retrieve(query_bundle)

        if not results:
            return []

        top_score = max(float(results[0].score or 0.0), 1e-9)

        chunks = []
        for position, result in enumerate(results, start=1):
            metadata = result.node.metadata or {}
            chunks.append({
                "id": result.node.node_id,
                "title": metadata.get("source_name") or self.source_name or "uploaded PDF",
                "body": result.node.get_content(),
                "page": metadata.get("page_label") or metadata.get("page"),
                "score": round(float(result.score or 0.0) / top_score, 3),
                "rank": position,
            })

        return chunks

    def answer(self, query: str, chunks: list[dict]) -> str:
        if not chunks:
            return (
                "I could not find relevant information in the uploaded PDF. "
                "Escalation is required."
            )

        if self.response_synthesizer is None:
            raise KnowledgeBaseNotInitialized(
                "The response synthesizer has not been initialized."
            )
        
        nodes = [
            NodeWithScore(
                node=TextNode(
                    text=chunk["body"],
                    metadata={
                        "title": chunk["title"],
                        "page": chunk.get("page"),
                    },
                ),
                score=float(chunk.get("score", 0.0)),
            )
            for chunk in chunks
        ]

        # Use the response synthesizer to generate a grounded answer based on the retrieved nodes.
        response = self.response_synthesizer.synthesize(
            query=query,
            nodes=nodes,
        )

        return str(response)

    @staticmethod
    def _resolve_pdf(source: str | Path) -> Path:
        source_text = str(source).strip()

        if source_text.startswith(("http://", "https://")):
            docs_dir = Path("docs")
            docs_dir.mkdir(parents=True, exist_ok=True)
            name = unquote(Path(urlparse(source_text).path).name) or "uploaded.pdf"

            if not name.lower().endswith(".pdf"):
                name += ".pdf"

            file_path = docs_dir / name
            response = requests.get(source_text, timeout=60)
            response.raise_for_status()

            if not response.content.startswith(b"%PDF"):
                raise ValueError("The URL did not return a valid PDF file")

            file_path.write_bytes(response.content)

            return file_path

        file_path = Path(source_text).expanduser().resolve()

        if not file_path.is_file():
            raise FileNotFoundError(f"PDF file does not exist: {file_path}")

        if file_path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a PDF file, received: {file_path.name}")

        return file_path


_kb: PDFKnowledgeBase | None = None
_kb_lock = Lock()


def _new_knowledge_base() -> PDFKnowledgeBase:
    return PDFKnowledgeBase(
        embed_model=os.getenv("EMBEDDING_MODEL"),
        llm_model=os.getenv("LLM_MODEL"),
        RAG_OLLAMA_URL=os.getenv("RAG_OLLAMA_URL"),
        chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "768")),
        chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "100")),
        storage_dir=os.getenv("RAG_STORAGE_DIR", "kb_storage"),
    )


def _configured_sources() -> list[str]:
    """Return configured PDFs in stable order without duplicates."""
    sources: list[str] = []
    configured = os.getenv("RAG_PDF_SOURCES", "")
    sources.extend(item.strip() for item in configured.split(";") if item.strip())

    default_directory = Path(__file__).resolve().parent / "docs"
    document_directory = Path(
        os.getenv("RAG_DOCUMENT_DIR", str(default_directory))
    ).expanduser()
    if document_directory.is_dir():
        sources.extend(
            str(path.resolve())
            for path in sorted(document_directory.glob("*.pdf"))
        )

    return list(dict.fromkeys(sources))


def initialize(source: str | Path | None = None) -> int:
    """Load an uploaded PDF, or restore the active persisted KB when omitted."""
    global _kb
    with _kb_lock:
        if source is None and _kb is not None:
            return _kb.node_count
        candidate = _new_knowledge_base()
        count = candidate.load(source) if source is not None else candidate.load_active()
        _kb = candidate
        return count


def initialize_documents() -> int:
    """Load every configured PDF once when the agent process starts."""
    global _kb
    sources = _configured_sources()
    if not sources:
        raise KnowledgeBaseNotInitialized(
            "No PDFs were found. Add PDFs to model/docs or set RAG_PDF_SOURCES."
        )

    with _kb_lock:
        candidate = _new_knowledge_base()
        for source in sources:
            candidate.load(source)
        _kb = candidate
        return candidate.node_count


def _get_kb() -> PDFKnowledgeBase:
    """Return the startup-loaded knowledge base, loading it if necessary."""
    if _kb is None:
        initialize_documents()
    assert _kb is not None
    return _kb


def search(query: str, category: str = "general") -> list[dict]:
    """Search the uploaded PDF. Category is included as retrieval context."""
    kb = _get_kb()
    return kb.search(f"IT category: {category}\nUser request: {query}")


def generate_answer(query: str, chunks: list[dict]) -> str:
    """Generate a grounded response from previously retrieved chunks."""
    return _get_kb().answer(query, chunks)

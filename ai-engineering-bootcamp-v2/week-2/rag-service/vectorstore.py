"""
Step 2 — the vector store seam.

Everything that knows about Pinecone lives here, so `main.py` stays a web layer and the
embedding settings are stated in exactly one place. Steps 3-5 import from this module.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec

# Same pattern as main.py — find .env next to this file, not next to the shell's cwd.
load_dotenv(Path(__file__).resolve().parent / ".env")

# The embedding model turns text into a vector. It must be identical at ingest time and at
# query time: two models produce vectors in different "spaces", so mixing them makes every
# similarity score meaningless. Pick once, never change without re-indexing everything.
EMBED_MODEL = "text-embedding-3-small"

# text-embedding-3-small emits 1536 numbers per vector. The index is created with this exact
# width, and Pinecone rejects any vector that does not match it.
EMBED_DIM = 1536

# Cosine measures the *angle* between two vectors, ignoring their length — which is what
# "these two passages mean similar things" translates to for OpenAI embeddings.
METRIC = "cosine"

# Serverless free tier is only offered in aws/us-east-1.
CLOUD, REGION = "aws", "us-east-1"

INDEX_NAME = os.getenv("PINECONE_INDEX", "northwind-rag")

# Chunking (Step 3). ~800 characters is roughly a paragraph — big enough to hold one
# complete idea, small enough that its vector isn't an average of several. The overlap
# carries sentences across boundaries so a fact split by the cut is still retrievable.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Pinecone limits how much a single upsert request may carry.
UPSERT_BATCH = 100


@lru_cache(maxsize=1)
def get_client() -> Pinecone:
    """
    One authenticated control-plane client for the whole process — same reasoning as the
    single AsyncOpenAI client in main.py: rebuilding it per request repeats the TLS
    handshake on every call. Cached lazily, so importing this module never needs the key
    and a missing key surfaces as a readable error at first use, not at startup.
    """

    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY is not set — add it to week-2/rag-service/.env")
    return Pinecone(api_key=api_key)


@lru_cache(maxsize=1)
def get_index():
    """
    Data-plane handle, cached for the process. `Index()` resolves the index's dedicated host
    via the control plane, so caching also avoids that extra lookup on every request.

    Connect only — creation is the one-time job of setup_index.py.
    """

    return get_client().Index(INDEX_NAME)


def _reset_caches() -> None:
    """Drop cached handles — used by setup_index.py after creating the index."""

    get_client.cache_clear()
    get_index.cache_clear()


# --------------------------------------------------------------------------- Step 3: write


@lru_cache(maxsize=1)
def get_openai() -> AsyncOpenAI:
    """Async client, cached for the same reason as the Pinecone one — no repeated handshakes."""

    return AsyncOpenAI()


def chunk_text(text: str) -> list[str]:
    """
    One document -> several passages.

    A whole document embedded as one vector averages every topic in it into a single blurry
    point, so a question about remote work retrieves the entire handbook. Passage-sized
    chunks each represent one idea, so retrieval returns the paragraph that answers the
    question. The overlap keeps a sentence that straddles a boundary from being orphaned.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # Try paragraph breaks first, then lines, then sentences — split at the most
        # natural boundary that fits, rather than mid-word at a fixed offset.
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c for c in splitter.split_text(text) if c.strip()]


async def embed(texts: list[str]) -> list[list[float]]:
    """
    Text -> vectors, in one batched API call rather than one call per chunk.

    The same function serves ingest and query, which is the point: it is structurally
    impossible for the two sides to use different models and silently produce garbage.
    """

    resp = await get_openai().embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def chunk_id(document_id: str, index: int) -> str:
    """Deterministic ID so re-ingesting a document overwrites its chunks instead of duplicating."""

    return f"{document_id}#{index}"


def delete_document(document_id: str) -> int:
    """
    Remove every chunk of one document. Returns how many were deleted.

    Serverless indexes do not support delete-by-metadata-filter, so we list IDs by prefix —
    which is exactly what the `document_id#n` naming convention above was chosen to enable.
    """

    index = get_index()
    # list() pages yield ListItem objects, not plain strings — delete() needs the raw ids.
    ids = [item.id for page in index.list(prefix=f"{document_id}#") for item in page]
    if ids:
        index.delete(ids=ids)
    return len(ids)


def upsert_chunks(
    document_id: str, chunks: list[str], vectors: list[list[float]], source: str
) -> int:
    """Write passages to Pinecone: the vector is searched, the metadata is what we can quote."""

    records = [
        {
            "id": chunk_id(document_id, i),
            "values": vector,
            "metadata": {
                "document_id": document_id,
                "chunk_index": i,
                "source": source,
                # The embedding is one-way, so the text must be carried alongside it or a
                # retrieved match could never be quoted into the prompt or shown as a citation.
                "text": chunk,
            },
        }
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    # Batched — Pinecone caps a single upsert request's payload size.
    for start in range(0, len(records), UPSERT_BATCH):
        get_index().upsert(vectors=records[start : start + UPSERT_BATCH])
    return len(records)


# ---------------------------------------------------------------------------- Step 4: read


async def search(question: str, top_k: int = 5) -> list[dict]:
    """
    Embed a question and return the closest passages, best match first.

    Deliberately contains no LLM call. Retrieval has to be verifiable on its own, because
    a wrong answer is far more often a retrieval failure than a generation failure.
    """

    query_vector = (await embed([question]))[0]
    result = get_index().query(vector=query_vector, top_k=top_k, include_metadata=True)

    return [
        {
            "chunk_id": match["id"],
            # Cosine similarity, 0-1 here. Higher is closer in meaning.
            "score": round(float(match["score"]), 4),
            "document_id": match["metadata"].get("document_id"),
            "chunk_index": match["metadata"].get("chunk_index"),
            "source": match["metadata"].get("source"),
            "text": match["metadata"].get("text", ""),
        }
        for match in result.get("matches", [])
    ]


def index_stats() -> dict:
    """
    Round-trip proof: we authenticated, the index exists, and we can read from it.
    Returns the vector count, which is 0 until Step 3 ingests anything.
    """

    stats = get_index().describe_index_stats()
    return {
        "index": INDEX_NAME,
        "dimension": stats.get("dimension"),
        "metric": METRIC,
        "total_vector_count": stats.get("total_vector_count", 0),
        "embed_model": EMBED_MODEL,
    }


def create_index_if_missing() -> bool:
    """Create the index with our exact settings. Returns True if it had to be created."""

    pc = get_client()
    if pc.has_index(INDEX_NAME):
        return False

    pc.create_index(
        name=INDEX_NAME,
        dimension=EMBED_DIM,
        metric=METRIC,
        spec=ServerlessSpec(cloud=CLOUD, region=REGION),
    )
    # A cached handle from before creation would point at an index that did not exist.
    _reset_caches()
    return True

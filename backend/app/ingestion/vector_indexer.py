"""Index filing chunks into a persistent ChromaDB collection and query it."""

from app.observability import traced
import argparse
from functools import lru_cache

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings
from app.ingestion.filing_loader import load_directory

BATCH = 128


@lru_cache(maxsize=1)
def default_collection():
    """Process-wide handle to the production collection (loads the embedding model once)."""
    return get_collection()


def get_collection(chroma_dir=None, name: str | None = None):
    client = chromadb.PersistentClient(path=str(chroma_dir or settings.chroma_dir))
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)
    return client.get_or_create_collection(
        name=name or settings.chroma_collection,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def index_chunks(chunks: list[dict], collection=None) -> int:
    collection = collection or default_collection()
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        collection.upsert(  # upsert => re-running ingestion is idempotent
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
        )
    return len(chunks)


def indexed_accessions(ticker: str, collection=None) -> set[str]:
    """Accession numbers of filings already indexed for ``ticker``."""
    collection = collection or default_collection()
    res = collection.get(where={"ticker": ticker.upper()}, include=["metadatas"])
    return {m["accession"] for m in res["metadatas"] if m.get("accession")}


def indexed_periods(ticker: str, collection=None) -> set[str]:
    """``period_end`` dates (ISO) indexed for ``ticker``."""
    collection = collection or default_collection()
    res = collection.get(where={"ticker": ticker.upper()}, include=["metadatas"])
    return {m["period_end"] for m in res["metadatas"] if m.get("period_end")}


def latest_period(ticker: str, collection=None) -> str | None:
    """Newest ``period_end`` indexed for ``ticker`` (ISO dates sort lexicographically)."""
    periods = indexed_periods(ticker, collection)
    return max(periods) if periods else None


@traced("chroma.search")
def search(
    query: str,
    k: int = 3,
    ticker: str | None = None,
    collection=None,
    period_end: str | None = None,
) -> list[dict]:
    collection = collection or default_collection()
    conds = []
    if ticker:
        conds.append({"ticker": ticker.upper()})
    if period_end:
        conds.append({"period_end": period_end})
    where = None if not conds else conds[0] if len(conds) == 1 else {"$and": conds}
    res = collection.query(query_texts=[query], n_results=k, where=where)
    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingest data/raw_filings/*.htm 10-Q filings into ChromaDB")
    ap.add_argument("--query", help="Optional test query after indexing")
    ap.add_argument("--ticker")
    args = ap.parse_args()

    chunks = load_directory()
    print(f"Loaded {len(chunks)} chunks from {settings.raw_filings_dir}")
    if chunks:
        print(f"Indexed {index_chunks(chunks)} chunks")
    if args.query:
        for r in search(args.query, ticker=args.ticker):
            m = r["metadata"]
            print(f"\n[{m['ticker']} 10-Q {m['period_end']} | {m['section']}] dist={r['distance']:.3f}")
            print(r["text"][:300])

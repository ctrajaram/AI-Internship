"""
Step 6 — batch-ingest every document in corpus/ through the running API.

    python ingest_corpus.py                        # against local server
    python ingest_corpus.py https://your.onrender.com

Calls the same POST /ingest the UI does, rather than writing to Pinecone directly, so the
API stays the single source of truth for how a document gets chunked and stored.
"""

import sys
from pathlib import Path

import httpx

CORPUS = Path(__file__).resolve().parent / "corpus"


def document_id_for(path: Path) -> str:
    """
    Stable ID derived from the filename: 'POL-101-employee-handbook.txt' -> 'POL-101'.

    Stable matters — it is what lets a re-ingest replace the old chunks instead of
    duplicating them, and it is what appears in citations.
    """

    return path.stem.split("-", 2)[0] + "-" + path.stem.split("-", 2)[1]


def main() -> None:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
    files = sorted(p for p in CORPUS.glob("*.txt"))
    if not files:
        raise SystemExit(f"No .txt files in {CORPUS}")

    print(f"Ingesting {len(files)} file(s) -> {base}/ingest\n")
    total = 0
    with httpx.Client(timeout=120) as http:
        for path in files:
            doc_id = document_id_for(path)
            resp = http.post(
                f"{base}/ingest",
                json={
                    "text": path.read_text(encoding="utf-8"),
                    "document_id": doc_id,
                    "source": path.name,
                },
            )
            if resp.status_code != 200:
                print(f"  FAIL {path.name}: {resp.status_code} {resp.text}")
                continue
            data = resp.json()
            total += data["chunks_indexed"]
            print(
                f"  {path.name:<40} -> {doc_id:<10} "
                f"{data['chunks_indexed']} chunks indexed, {data['chunks_replaced']} replaced"
            )

    print(f"\nTotal chunks indexed: {total}")
    print(f"Verify: {base}/debug/health")


if __name__ == "__main__":
    main()

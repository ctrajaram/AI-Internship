"""
Run once: create the Pinecone index this service expects.

    python setup_index.py

Safe to re-run — it creates nothing if the index already exists. Kept out of main.py so a
cold start never waits on index creation, and a Pinecone hiccup can't stop the API booting.
"""

import time

import vectorstore


def main() -> None:
    print(f"Index name : {vectorstore.INDEX_NAME}")
    print(f"Dimension  : {vectorstore.EMBED_DIM}  (fixed by {vectorstore.EMBED_MODEL})")
    print(f"Metric     : {vectorstore.METRIC}")
    print(f"Region     : {vectorstore.CLOUD}/{vectorstore.REGION}")

    if vectorstore.create_index_if_missing():
        print("\nCreating... (serverless indexes take ~30s to become ready)")
        # describe_index_stats() errors until the index finishes provisioning, so poll.
        for _ in range(60):
            try:
                vectorstore.index_stats()
                break
            except Exception:
                time.sleep(2)
        else:
            raise SystemExit("Index did not become ready in 120s — check the Pinecone console.")
        print("Created.")
    else:
        print("\nAlready exists — nothing to do.")

    print("\nReady.")
    print(vectorstore.index_stats())


if __name__ == "__main__":
    main()

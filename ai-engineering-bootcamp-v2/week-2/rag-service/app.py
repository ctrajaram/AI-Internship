"""
Step 9 — Streamlit UI for the RAG service.

    streamlit run app.py

A thin client on purpose: it holds no keys, does no chunking, no embedding, no retrieval.
Every one of those decisions lives in the FastAPI service, so the UI and the curl commands
can never disagree about what the system does.
"""

import os

import httpx
import streamlit as st

DEFAULT_API = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Week 2 — RAG Q&A", page_icon="📄", layout="centered")
st.title("📄 Northwind RAG")
st.caption("Ask questions answered only from ingested documents — with citations, or a refusal.")

with st.sidebar:
    st.header("Connection")
    api_base = st.text_input("API base URL", value=DEFAULT_API).rstrip("/")
    if st.button("Check vector store"):
        try:
            r = httpx.get(f"{api_base}/debug/health", timeout=30)
            st.success(r.json()) if r.status_code == 200 else st.error(r.text)
        except Exception as exc:
            st.error(f"Unreachable: {exc}")
    st.caption("No API keys live here — the service holds them.")

ingest_tab, ask_tab, retrieve_tab = st.tabs(["📥 Ingest", "❓ Ask", "🔍 Retrieval debug"])


with ingest_tab:
    st.subheader("Add a document")
    doc_id = st.text_input("document_id", value="POL-101", help="Appears in citations. Re-using an ID replaces that document.")
    text = st.text_area("Document text", height=260, placeholder="Paste the document contents here...")

    if st.button("Ingest", type="primary"):
        if not text.strip() or not doc_id.strip():
            st.warning("Both document_id and text are required.")
        else:
            with st.spinner("Chunking, embedding, upserting..."):
                try:
                    r = httpx.post(
                        f"{api_base}/ingest",
                        json={"text": text, "document_id": doc_id, "source": f"{doc_id} (ui)"},
                        timeout=180,
                    )
                except Exception as exc:
                    st.error(f"Request failed: {exc}")
                else:
                    if r.status_code == 200:
                        d = r.json()
                        st.success(
                            f"Indexed {d['chunks_indexed']} chunks for **{d['document_id']}** "
                            f"(replaced {d['chunks_replaced']} old chunks)"
                        )
                        st.json(d)
                    else:
                        st.error(f"{r.status_code}: {r.text}")


with ask_tab:
    st.subheader("Ask a question")
    question = st.text_input("Question", value="How many days can I work from home?")
    col1, col2 = st.columns(2)
    model = col1.selectbox("Model", ["gpt-4o-mini", "gpt-4o"], index=0)
    top_k = col2.slider("Chunks retrieved (k)", 1, 10, 5)

    if st.button("Ask", type="primary"):
        with st.spinner("Retrieving, then answering..."):
            try:
                r = httpx.post(
                    f"{api_base}/ask",
                    json={"question": question, "model": model, "top_k": top_k},
                    timeout=180,
                )
            except Exception as exc:
                st.error(f"Request failed: {exc}")
            else:
                if r.status_code != 200:
                    st.error(f"{r.status_code}: {r.text}")
                else:
                    d = r.json()
                    ans = d["answer"]
                    citations = ans.get("citations", [])

                    # A refusal is a success, not an error — show it as clearly distinct
                    # from a grounded answer so the difference is visible at a glance.
                    if citations:
                        st.success(ans["answer"])
                        st.markdown("**Sources:** " + " ".join(f"`{c}`" for c in citations))
                    else:
                        st.warning(ans["answer"])
                        st.caption("No citations — the retrieved context did not contain the answer.")

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Tokens", d["tokens_used"])
                    m2.metric("Cost (USD)", f"${d['cost_usd']:.6f}")
                    m3.metric("Latency", f"{d['latency_ms']} ms")

                    with st.expander(f"Context the model was given ({len(d['chunk_ids'])} chunks)"):
                        for m in d["retrieved"]:
                            st.markdown(f"**`{m['chunk_id']}`** · score `{m['score']}` · {m['source']}")
                            st.text(m["text"])
                            st.divider()

                    with st.expander("Raw JSON response"):
                        st.json(d)


with retrieve_tab:
    st.subheader("Retrieval only — no LLM")
    st.caption("If the right passage isn't here, no prompt change will fix the answer.")
    q = st.text_input("Query", value="remote work", key="retrieve_q")
    rk = st.slider("Top k", 1, 10, 5, key="retrieve_k")

    if st.button("Retrieve"):
        try:
            r = httpx.get(f"{api_base}/debug/retrieve", params={"q": q, "k": rk}, timeout=60)
        except Exception as exc:
            st.error(f"Request failed: {exc}")
        else:
            if r.status_code != 200:
                st.error(f"{r.status_code}: {r.text}")
            else:
                matches = r.json()["matches"]
                if not matches:
                    st.warning("No matches — has anything been ingested?")
                for m in matches:
                    st.markdown(f"**`{m['chunk_id']}`** · score `{m['score']}` · {m['source']}")
                    st.text(m["text"])
                    st.divider()

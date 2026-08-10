# Week 2 — RAG service

The Week 1 `/ask` service, extended with retrieval. Week 1 answered from the model's own
training data; this service answers **only** from documents you ingest, and cites them.

```
question ──► embed ──► search Pinecone ──► context + question ──► LLM ──► answer + citations
```

## Status

Built one step at a time. Current state: **Step 1 — scaffold**.

| Step | What it adds | Done |
|------|--------------|------|
| 1 | Scaffold: Week 1 `/ask` running here unchanged | ✅ |
| 2 | Pinecone client + `GET /debug/health` | ✅ |
| 3 | `POST /ingest` — chunk, embed, upsert | ☐ |
| 4 | `GET /debug/retrieve` — search with no LLM | ☐ |
| 5 | `/ask` upgraded to RAG with citations + refusal | ☐ |
| 6 | Batch corpus ingest script | ☐ |
| 7 | Render deployment | ☐ |
| 8 | Cited-answer + refusal transcripts | ☐ |
| 9 | Streamlit UI | ☐ |

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # then paste your keys
```

## Run

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is RAG in one sentence?","model":"gpt-4o-mini"}'
```

Interactive docs: http://127.0.0.1:8000/docs

## Relationship to `week-1/`

`week-1/` stays frozen as the finished Session 1 submission. This folder is a copy of
`week-1/main.py` that Week 2 grows into a RAG service, so the two can be run and compared
side by side.

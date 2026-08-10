# Week 2 — RAG submission evidence

Captured against the local service on 2026-08-10. Replace `$BASE` with the live Render URL
to reproduce these against the deployed service.

```bash
BASE=http://127.0.0.1:8000        # or https://<your-service>.onrender.com
```

Corpus indexed: `POL-101` (employee handbook), `SEC-204` (security policy) — 3 chunks total.

---

## 1. Vector store health

```bash
curl -s $BASE/debug/health
```

```json
{
  "vector_store": "ok",
  "index": "northwind-rag",
  "dimension": 1536,
  "metric": "cosine",
  "total_vector_count": 3,
  "embed_model": "text-embedding-3-small"
}
```

## 2. Ingest

```bash
curl -s -X POST $BASE/ingest \
  -H "Content-Type: application/json" \
  -d '{"document_id":"POL-101","text":"Northwind Robotics Employee Handbook...","source":"POL-101-employee-handbook.txt"}'
```

```json
{"document_id":"POL-101","chunks_indexed":1,"chunks_replaced":1,"status":"ok"}
```

`chunks_replaced` proves re-ingest overwrites rather than duplicates — running
`python ingest_corpus.py` twice leaves the index at 3 chunks, not 6.

## 3. Retrieval proven before generation

No LLM is involved in this endpoint.

```bash
curl -s "$BASE/debug/retrieve?q=how+many+days+can+I+work+from+home&k=3"
```

```
score   chunk        text
0.4052  POL-101#0    'Northwind Robotics Employee Handbook...'
0.2695  SEC-204#1    'Customer data may not be copied to personal devices...'
0.2178  SEC-204#0    'Northwind Robotics Information Security Policy...'
```

```bash
curl -s "$BASE/debug/retrieve?q=how+long+must+my+password+be&k=3"
```

```
score   chunk        text
0.5459  SEC-204#0    'Northwind Robotics Information Security Policy...'
0.3271  SEC-204#1    'Customer data may not be copied to personal devices...'
0.1538  POL-101#0    'Northwind Robotics Employee Handbook...'
```

The two queries rank the two documents in opposite orders — retrieval discriminates by
meaning, not keywords ("from home" never appears in the handbook).

## 4. Cited answer

```bash
curl -s -X POST $BASE/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"How many days per week can I work remotely?","model":"gpt-4o-mini"}'
```

```json
{
  "answer": {
    "answer": "You may work remotely up to three days per week.",
    "confidence": 1.0,
    "sources_needed": false,
    "citations": ["POL-101"]
  },
  "tokens_used": 494,
  "model": "gpt-4o-mini",
  "latency_ms": 1205,
  "cost_usd": 8.8e-05,
  "chunk_ids": ["POL-101#0", "SEC-204#0", "SEC-204#1"]
}
```

A second one, landing on the other document:

```json
{
  "answer": {
    "answer": "Passwords must be at least 14 characters and are rotated every 180 days. Password reuse is blocked for the previous 10 passwords.",
    "confidence": 0.9,
    "sources_needed": false,
    "citations": ["SEC-204"]
  },
  "tokens_used": 508,
  "cost_usd": 9.8e-05,
  "chunk_ids": ["SEC-204#0", "SEC-204#1", "POL-101#0"]
}
```

## 5. Refusal

```bash
curl -s -X POST $BASE/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the parental leave policy?","model":"gpt-4o-mini"}'
```

```json
{
  "answer": {
    "answer": "I don't have enough information to answer that.",
    "confidence": 0.0,
    "sources_needed": false,
    "citations": []
  },
  "tokens_used": 485,
  "model": "gpt-4o-mini",
  "latency_ms": 864,
  "cost_usd": 8.4e-05,
  "chunk_ids": ["POL-101#0", "SEC-204#0", "SEC-204#1"]
}
```

Note `chunk_ids` is non-empty while `citations` is empty: chunks *were* retrieved, and the
model correctly judged that none of them answered the question. Week 1's `/ask` would have
answered this from training data with no way to signal that the source documents were silent.

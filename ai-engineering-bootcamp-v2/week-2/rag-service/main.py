"""Week 1 live demo — five stages in one file, built up live in class."""

import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError

import vectorstore  # Week 2 — Pinecone settings and connection live in one module.

# Load .env from this folder so the key is found regardless of shell working directory.
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)

# Reuse one client so TLS handshakes are not repeated on every request.
app = FastAPI()

# Async client, paired with `async def` endpoints below. FastAPI runs a plain `def` endpoint
# in a bounded worker thread pool, so every in-flight request holds a thread for the whole
# 1-3 second OpenAI call and concurrency is capped by that pool. An `async def` endpoint
# awaiting an async client holds no thread while waiting on the network, so one process can
# serve many simultaneous requests.
client = AsyncOpenAI()  # Reads OPENAI_API_KEY from the environment; never hardcode keys.

# Stage 4 default — strong general model; swap at request time for the live demo.
DEFAULT_MODEL = "gpt-4o"

# Stage 5 — per-1K-token input/output USD (derived from OpenAI list prices).
MODEL_PRICES_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "o3-mini": (0.0011, 0.0044),
}


REFUSAL = "I don't have enough information to answer that."

# Week 2 — the grounding prompt. Everything that makes this RAG rather than a chatbot is
# here: answer only from what was retrieved, refuse rather than guess, name your sources.
GROUNDING_PROMPT = """Answer using ONLY the context below. If the context lacks the answer, \
set answer to exactly: "{refusal}"
Cite the document_id of each chunk you used in the citations field. Cite nothing if you refuse.

CONTEXT:
{context}

QUESTION: {question}"""


class Answer(BaseModel):
    """Structured model output — this is what turns a chatbot into a component."""

    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources_needed: bool
    # Week 2 — which documents the answer came from. Empty on a refusal, which is what
    # makes "grounded" checkable instead of a claim we take on trust.
    citations: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    """Typed request body so bad input is rejected before we spend tokens."""

    question: str
    force_bad: bool = False  # Stage 3 demo knob — first attempt breaks schema on purpose.
    # Stage 4 — optional override to swap models live. The example keeps the docs
    # from prefilling "string", which would reach the API as a real model name.
    model: str | None = Field(default=None, examples=["gpt-4o-mini"])
    # Week 2 — how many passages to retrieve. 5 is a good default: enough for the answer to
    # be present, few enough that the prompt isn't padded with near-misses.
    top_k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    """Typed response so callers always get the same shape back."""

    answer: Answer
    tokens_used: int
    model: str
    latency_ms: int
    cost_usd: float
    # Week 2 — the exact passages that were put in front of the model. Lets a caller audit
    # a bad answer without re-running anything: was it retrieved wrong, or read wrong?
    chunk_ids: list[str] = Field(default_factory=list)
    retrieved: list[dict] = Field(default_factory=list)


class IngestRequest(BaseModel):
    """A document arrives as plain text — no file upload, so any client can call this."""

    text: str
    document_id: str
    source: str | None = None


class IngestResponse(BaseModel):
    document_id: str
    chunks_indexed: int
    chunks_replaced: int
    status: str


def compute_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Turn real usage into dollars — same prompt, different model, different cost."""

    prices = MODEL_PRICES_PER_1K.get(model, MODEL_PRICES_PER_1K[DEFAULT_MODEL])
    input_per_1k, output_per_1k = prices
    return (prompt_tokens / 1000 * input_per_1k) + (completion_tokens / 1000 * output_per_1k)


async def call_model_structured(prompt: str, model: str) -> tuple[Answer, int, int, int]:
    """
    Stage 2 center: OpenAI structured output forces exactly the Answer schema.
    Returns parsed answer plus token counts from billing metadata.

    Week 2 changed only what `prompt` contains — a grounded prompt instead of a bare
    question. The structured-output machinery is untouched.
    """

    completion = await client.chat.completions.parse(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format=Answer,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("Model returned no parseable structured output")

    usage = completion.usage
    total = usage.total_tokens if usage else 0
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    return parsed, total, prompt_tokens, completion_tokens


async def call_model_unsafe(question: str, model: str) -> tuple[Answer, int, int, int]:
    """
    Stage 3 demo path: free-form JSON call, then validate locally.
    The bad instruction makes confidence a string so Pydantic rejects it reliably.
    """

    completion = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{question}\n\n"
                    "Reply with ONLY a JSON object using keys answer, confidence, sources_needed. "
                    "Set confidence to the string 'very high' (not a number)."
                ),
            }
        ],
    )

    raw = completion.choices[0].message.content or ""
    # Guardrail: refuse malformed output instead of passing it through to clients.
    answer = Answer.model_validate_json(raw)

    usage = completion.usage
    total = usage.total_tokens if usage else 0
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    return answer, total, prompt_tokens, completion_tokens


@app.get("/debug/health")
async def debug_health() -> dict:
    """
    Step 2 — is the vector store reachable? Deliberately touches no LLM and no documents,
    so a failure here can only mean credentials, index name, or network.
    """

    try:
        return {"vector_store": "ok", **vectorstore.index_stats()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Vector store unreachable: {exc}") from exc


@app.post("/ingest")
async def ingest(body: IngestRequest) -> IngestResponse:
    """Step 3 — text in, searchable vectors out. The write half of RAG."""

    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    if not body.document_id.strip():
        raise HTTPException(status_code=400, detail="document_id must not be empty")

    chunks = vectorstore.chunk_text(body.text)
    if not chunks:
        raise HTTPException(status_code=400, detail="text produced no usable chunks")

    try:
        vectors = await vectorstore.embed(chunks)
        # Replace, don't append: without this, re-ingesting an edited document leaves the
        # old passages in the index competing with the new ones, and a stale sentence can
        # win the search and get cited as current.
        replaced = vectorstore.delete_document(body.document_id)
        indexed = vectorstore.upsert_chunks(
            body.document_id, chunks, vectors, body.source or body.document_id
        )
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Vector store write failed: {exc}") from exc

    return IngestResponse(
        document_id=body.document_id,
        chunks_indexed=indexed,
        chunks_replaced=replaced,
        status="ok",
    )


@app.get("/debug/retrieve")
async def debug_retrieve(q: str, k: int = 5) -> dict:
    """
    Step 4 — retrieval on its own, with no LLM anywhere near it.

    The most common RAG failure is a wrong answer caused by wrong retrieval, then debugged
    as if it were a prompting problem. This endpoint makes retrieval falsifiable by itself:
    if the right chunk isn't in this list, no amount of prompt tuning will save /ask.
    """

    if not q.strip():
        raise HTTPException(status_code=400, detail="q must not be empty")

    try:
        matches = await vectorstore.search(q, top_k=k)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Retrieval failed: {exc}") from exc

    return {"query": q, "top_k": k, "matches": matches}


@app.post("/ask")
async def ask(body: AskRequest) -> AskResponse:
    """
    Week 2 — retrieve first, then answer only from what was retrieved.

    Week 1 sent the question straight to the model, which answered from training data with
    no way to say "that isn't in my sources". Now the model sees the question wrapped in
    retrieved context, so every answer is either grounded and cited, or refused.
    """

    model = body.model or DEFAULT_MODEL
    last_error: str | None = None

    # Retrieval happens once, outside the retry loop — a schema retry should not re-run
    # (and re-bill) the embedding and the vector search.
    try:
        matches = await vectorstore.search(body.question, top_k=body.top_k)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Retrieval failed: {exc}") from exc

    chunk_ids = [m["chunk_id"] for m in matches]

    # Nothing indexed, or nothing close enough — refuse without spending a token. The model
    # can only be trusted to refuse when given no context if we never ask it in the first place.
    if not matches:
        return AskResponse(
            answer=Answer(answer=REFUSAL, confidence=1.0, sources_needed=True, citations=[]),
            tokens_used=0,
            model=model,
            latency_ms=0,
            cost_usd=0.0,
            chunk_ids=[],
            retrieved=[],
        )

    context = "\n\n".join(f"[{m['document_id']} · {m['chunk_id']}]\n{m['text']}" for m in matches)
    prompt = GROUNDING_PROMPT.format(refusal=REFUSAL, context=context, question=body.question)

    # Stage 3: one retry keeps the logic legible while still protecting callers.
    for attempt in range(2):
        try:
            start = time.perf_counter()

            # First attempt with force_bad uses the unsafe path; retry uses structured output.
            use_bad_path = body.force_bad and attempt == 0
            if use_bad_path:
                answer, tokens_used, prompt_tokens, completion_tokens = await call_model_unsafe(
                    prompt, model
                )
            else:
                answer, tokens_used, prompt_tokens, completion_tokens = await call_model_structured(
                    prompt, model
                )

            latency_ms = int((time.perf_counter() - start) * 1000)
            cost_usd = compute_cost_usd(model, prompt_tokens, completion_tokens)

            # Guardrail: a citation the model invented is worse than no citation, so keep
            # only the document_ids that were actually retrieved for this question.
            retrieved_docs = {m["document_id"] for m in matches}
            answer.citations = [c for c in dict.fromkeys(answer.citations) if c in retrieved_docs]

            return AskResponse(
                answer=answer,
                tokens_used=tokens_used,
                model=model,
                latency_ms=latency_ms,
                cost_usd=round(cost_usd, 6),
                chunk_ids=chunk_ids,
                retrieved=matches,
            )
        except OpenAIError as exc:
            # Upstream refused the call (bad model name, auth, rate limit) — retrying
            # the same request will not help, so fail loudly instead of silently.
            raise HTTPException(
                status_code=502, detail=f"Model call failed for {model!r}: {exc}"
            ) from exc
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            continue

    # Clean failure — never leak a half-parsed response to the client.
    raise HTTPException(
        status_code=502,
        detail=f"Model response failed schema validation after retry: {last_error}",
    )

"""
The entire RAG loop in one file, printing every intermediate value.

Uses plain Python lists instead of Pinecone, so you can see the mechanism without the
database in the way. Pinecone's only job in the real thing is doing step 4 fast over
millions of chunks instead of 4.
"""

import math
import textwrap

from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI

import vectorstore

client = OpenAI()
DOC_ID = "POL-101"
RULE = "=" * 78


def banner(n, title):
    print(f"\n{RULE}\n{n}. {title}\n{RULE}")


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


# ---------------------------------------------------------------- 1. the document
banner(1, "THE DOCUMENT  (one string, read off disk)")
doc = open("corpus/POL-101-employee-handbook.txt", encoding="utf-8").read()
print(doc)

# ---------------------------------------------------------------- 2. chunking
banner(2, "CHUNKING  (one string  ->  several passages)")
# 200 chars here only so this short handbook produces several chunks to look at.
# The real /ingest uses 800/100.
splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=40)
chunks = splitter.split_text(doc)
for i, c in enumerate(chunks):
    print(f"\n[{DOC_ID}#{i}]  {len(c)} chars")
    print(textwrap.indent(c, "    "))

# ---------------------------------------------------------------- 3. embedding
banner(3, "EMBEDDING  (each passage -> 1536 numbers)  <- this is 'vectoring'")
resp = client.embeddings.create(model=vectorstore.EMBED_MODEL, input=chunks)
chunk_vecs = [d.embedding for d in resp.data]
print(f"one API call, {len(chunks)} passages in, {len(chunk_vecs)} vectors out, "
      f"{resp.usage.total_tokens} tokens\n")
for i, v in enumerate(chunk_vecs):
    print(f"[{DOC_ID}#{i}] -> [{v[0]:+.4f}, {v[1]:+.4f}, {v[2]:+.4f}, ... ] ({len(v)} floats)")
print("\nIn the real service these vectors are what gets stored in Pinecone,")
print("with the passage text carried alongside as metadata.")


def ask(question, k=2):
    # ------------------------------------------------------------ 4. retrieval
    banner(4, f"RETRIEVAL for: {question!r}")
    qvec = client.embeddings.create(model=vectorstore.EMBED_MODEL, input=question).data[0].embedding
    print("The question is embedded with the SAME model -> 1536 numbers, same space.\n")

    scored = sorted(
        ((cosine(qvec, v), i) for i, v in enumerate(chunk_vecs)), reverse=True
    )
    print("  score   chunk        first words")
    print("  " + "-" * 68)
    for score, i in scored:
        print(f"  {score:.4f}  {DOC_ID}#{i:<7} {chunks[i][:44].replace(chr(10), ' ')}...")

    top = scored[:k]
    print(f"\nTake the top {k}. No LLM has been involved yet — this is pure arithmetic.")

    # ------------------------------------------------------------ 5. the prompt
    banner(5, "THE PROMPT  (retrieval's ONLY output is text pasted into a prompt)")
    context = "\n\n".join(f"[{DOC_ID}#{i}]\n{chunks[i]}" for _, i in top)
    prompt = (
        "Answer using ONLY the context below. If the context lacks the answer, say "
        "exactly: 'I don't have enough information to answer that.' "
        "Cite the document_id of each chunk you used.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {question}"
    )
    print(prompt)

    # ------------------------------------------------------------ 6. generation
    banner(6, "GENERATION  (an ordinary LLM call — nothing special)")
    out = client.chat.completions.create(
        model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]
    )
    print(out.choices[0].message.content)


ask("How many days can I work from home?")

print("\n\n" + "#" * 78)
print("# Now a question the handbook does NOT answer")
print("#" * 78)
ask("What is the company parental leave policy?")

# Grounded RAG Assistant (demo)

A customer-facing "ask your documents" assistant that **only answers from the customer's own data**, **cites every answer** (document + page, or record ID), and **refuses** when the answer isn't there. It doesn't guess.

Built as a reference implementation of a common SaaS request: answer customers' questions from their own records and documents, in a streaming panel inside the app, with a question log and an admin page.

```
PDFs / web pages / records ──► ingest ──► per-customer index (vectors + BM25)
                                                   │
question + customer_id ──► hybrid retrieval ──► relevance gate ──► LLM (streamed, numbered citations)
                                                   │ (below threshold)        │
                                                   ▼                          ▼
                                         fixed refusal, no LLM call    citation check ──► log (tokens, cost, latency)
```

## What it does

| Requirement | How |
|---|---|
| Answer only from the customer's data | Each customer has its own index. Retrieval opens only that customer's index, so another tenant's data can't leak. `customer_id` must match `[A-Za-z0-9_-]{1,64}`, so it can't escape the index folder. With `CUSTOMER_TOKENS` set, each token can only query its own customer (403 otherwise). |
| Show the source of every answer | The model must tag each sentence with `[n]`. The server keeps only citations that point at chunks it actually supplied and returns them as `doc + page` or `record ID`. |
| Say "that isn't in your documents" | **Gate 1:** if the best embedding similarity is below `MIN_RELEVANCE` *and* the question names no exact identifier (e.g. `INV-1057`) found in a retrieved chunk, the fixed refusal is returned without calling the LLM. **Gate 2:** the prompt forbids general knowledge and requires the exact refusal text. |
| Flag ungrounded answers | An answer with no valid citation is marked `grounded: false` in the stream, the panel and the log. |
| Stream into the app | `POST /chat` returns Server-Sent Events (`token` events, then one `final` event with sources). |
| Guardrails | Token cap per answer, per-user rate limit, refusal gate, bearer-token auth. |
| Question log | Every question, answer, sources, refusal/grounded flags, tokens, cost (USD) and time-to-first-token is logged to SQLite. |
| Admin | `/admin`: edit the system prompt live and read the log. |
| No hard-coded keys or models | Everything is set in `.env`. Models go through LiteLLM, so OpenAI, Anthropic, Gemini, Azure etc. are a config change. |

## Stack

- **Ingestion:** PyMuPDF (keeps page numbers), Trafilatura (web pages), JSON records → ~180-word overlapping chunks
- **Retrieval:** dense embeddings + BM25, merged with reciprocal rank fusion. Exact figures and IDs ("INV-1057", "2%") are caught by BM25 when embeddings miss them.
- **Store:** NumPy + JSON per customer, so the demo needs no setup. For production, swap in Postgres + pgvector with the same `customer_id` filter.
- **API:** FastAPI + SSE. **LLM:** LiteLLM (provider-agnostic, streaming, cost tracking)
- **UI:** a dependency-free panel (`web/index.html`) and admin page. It's the same fetch-stream logic you'd drop into a React component.

## Setup (fresh clone)

```bash
git clone <this repo> && cd grounded-rag-demo
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # add your API key and model names
make ingest                                           # or: python -m app.ingest
make serve                                            # or: uvicorn app.main:app --port 8000
```

Open http://localhost:8000. Enter your `API_TOKEN`, pick a customer (`acme` or `globex`) and ask:
- *What is the late fee on rent?* → answer with `Acme_Office_Lease.pdf (page 2)`
- *Why was the October rent invoice higher?* → answer citing `record INV-1057`
- *What is the capital of France?* → refusal

Admin page: http://localhost:8000/admin (use `ADMIN_TOKEN`).

### Adding and re-indexing documents

- PDFs: `data/docs/<customer_id>/*.pdf`
- Web pages: `data/urls.txt`, one line per page: `<customer_id> <url>`
- Records: `data/records/<customer_id>.json` (a list of objects, each with an `id`)

`make ingest` skips customers whose files haven't changed. `make reindex` wipes the index and rebuilds everything. Run it after changing `EMBED_MODEL`.

### API

```bash
curl -N -X POST localhost:8000/chat \
  -H "Authorization: Bearer $API_TOKEN" -H "X-User-Id: u42" -H "Content-Type: application/json" \
  -d '{"customer_id":"acme","question":"What is the deductible on an own-damage claim?"}'
```
```
data: {"type": "token", "text": "The deductible"}
...
data: {"type": "final", "answer": "...", "sources": [{"n": 1, "label": "Acme_Fleet_Insurance.pdf (page 2)", ...}],
       "refused": false, "grounded": true, "first_token_ms": 640, "prompt_tokens": 812, "completion_tokens": 31, "cost_usd": 0.00014}
```
In a real app, `customer_id` comes from the logged-in session, not from the request body. Until then, set `CUSTOMER_TOKENS` so a token is bound to one customer; the shared `API_TOKEN` is for local demos only.

## Measuring grounding

```bash
make eval          # python -m eval.run_eval
make eval-judge    # also has the LLM check each answer is supported by its cited excerpts
```

`eval/questions.json` holds 12 test questions:
- **8 answerable** (from PDFs and records): scored for correct facts *and* citing the expected source
- **2 out-of-scope** (general knowledge, creative writing): must get the fixed refusal
- **1 cross-tenant** (Globex asking about Acme's lease): must be refused, which proves isolation
- **1 held-back document** (`data/holdout/` is never ingested): must say it's not in the documents

The report (`eval/report.md`) shows correctness, citation accuracy, refusal accuracy and first-token latency per question. Use it to tune `MIN_RELEVANCE` and the system prompt, and rerun it after every prompt change.

## Tests

`make test` runs offline (`local-hash` embeddings + a fake LLM, no key needed). It covers page-aware ingestion, the held-back document never being indexed, tenant isolation, citation mapping, flagging invalid citations, refusal without an LLM call, auth, rate limiting, logging and the admin prompt.

## Project layout

```
app/
  config.py     all settings, read from .env
  loaders.py    PDFs / web pages / records -> chunks          (bad page numbers, missing text)
  ingest.py     build the per-customer index (make ingest)    (stale or missing index)
  embed.py      embeddings via LiteLLM, or local-hash offline
  retrieve.py   hybrid search + exact-ID match, per customer  (wrong chunks retrieved)
  prompt.py     system prompt + numbered sources -> messages  (model ignores rules)
  llm.py        streaming model call, tokens and cost         (provider errors, cost = null)
  citations.py  refusal / valid-citation / grounded checks    (answer flagged ungrounded)
  rag.py        the pipeline: retrieve -> gate -> stream -> check -> log
  db.py         SQLite question log + editable system prompt
  auth.py       tokens (shared or per-customer) + rate limit  (401 / 403 / 429)
  admin.py      /admin/prompt and /admin/log API
  main.py       FastAPI app, POST /chat (SSE), HTML pages
web/   index.html (assistant panel)  admin.html
eval/  questions.json  run_eval.py
data/  docs/<customer>/  records/  holdout/  urls.txt
tests/ conftest.py (fixtures)  helpers.py (fake LLM)  test_ingest  test_retrieve  test_rag  test_api
```

All sample companies and documents are fictional (`scripts/make_sample_docs.py`).

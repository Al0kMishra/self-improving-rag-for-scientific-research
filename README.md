# Self-Improving RAG for Scientific Research Literature

A retrieval-augmented generation system that answers AI/ML research questions from **live arXiv papers**, cites every claim to the exact retrieved chunk, **evaluates its own answers**, and uses those evaluations plus user feedback to **change how it ranks evidence** for future questions. A Baseline RAG runs alongside it so the improvement can be measured on real experiments.

## Contents

- [Quick start](#quick-start)
- [Pipeline](#pipeline)
- [How each stage works](#how-each-stage-works)
- [The self-improvement mechanism](#the-self-improvement-mechanism)
- [Baseline vs proposed](#baseline-vs-proposed)
- [Experiments](#experiments)
- [Results](#results)
- [API](#api)
- [Project layout](#project-layout)
- [Configuration](#configuration)
- [Testing and conventions](#testing-and-conventions)
- [Limitations](#limitations)

## Quick start

Seven steps from a fresh machine to a running dashboard. Steps 1 to 4 take about 10 minutes, most of it downloads.

### Step 1: install the prerequisites

You need three tools. Check what you already have:

```bash
git --version        # any version
python3 --version    # 3.11 or newer
node --version       # 20 or newer
```

Install anything missing:

- **Git:** https://git-scm.com/downloads
- **Python 3.11+:** https://www.python.org/downloads (on macOS `brew install python@3.12` also works)
- **Node.js 20+:** https://nodejs.org (the LTS version)

On Windows, the simplest route is [Docker](#run-with-docker-instead) or WSL (`wsl --install`, then follow these steps inside Ubuntu). Manual Windows commands are under [Windows without Docker](#windows-without-docker).

### Step 2: download the project and run setup

```bash
git clone https://github.com/yashdagar/self-improving-rag.git
cd self-improving-rag
./scripts/setup.sh
```

`setup.sh` does everything once:

1. copies `.env.example` to `.env` (your private settings file, never committed)
2. creates a Python environment in `.venv` and installs the backend libraries (PyTorch, ChromaDB, PyMuPDF and so on, about 1 GB)
3. installs the dashboard's Node packages
4. downloads the embedding model (about 90 MB)
5. turns on the commit message check

It ends with `Done. Next:`. If it stops with an error, see [Troubleshooting](#troubleshooting).

### Step 3: choose your model and put its key in `.env`

The system uses an LLM for two jobs: **writing** the answer and **judging** it (self-evaluation). You can use one model for both, or a separate model for each. Open `.env` in any editor and fill in one of the setups below; leave every other line as it is.

Get a key from the provider you want:

- **Gemini:** https://aistudio.google.com/apikey (has a free tier)
- **Grok (xAI):** https://console.x.ai
- **Claude (Anthropic):** https://console.anthropic.com

#### Setup 1: one model for everything (simplest)

Fill in only the `LLM_` lines. The judge automatically uses the same model and key. Pick one provider:

Gemini:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-3.8-flash
LLM_API_KEY=paste-your-gemini-key-here
```

Grok:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.x.ai/v1
LLM_MODEL=grok-4.7
LLM_API_KEY=xai-paste-your-key-here
```

Claude:

```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-opus-5
LLM_API_KEY=sk-ant-paste-your-key-here
```

#### Setup 2: separate models for writing and judging

Add `EVALUATOR_` lines on top of Setup 1. Anything you leave empty is copied from the `LLM_` lines, so you only write what is different. A separate judge is better for the project, because a model grading its own answers can share its own blind spots.

Same provider, different model (one key), for example a light Gemini writes and a stronger Gemini judges:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-3.5-flash-lite
LLM_API_KEY=paste-your-gemini-key-here

EVALUATOR_MODEL=gemini-3.8-flash
```

Different providers (two keys), for example Grok writes and Gemini judges:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.x.ai/v1
LLM_MODEL=grok-4.7
LLM_API_KEY=xai-paste-your-key-here

EVALUATOR_PROVIDER=openai_compatible
EVALUATOR_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
EVALUATOR_MODEL=gemini-3.8-flash
EVALUATOR_API_KEY=paste-your-gemini-key-here
```

Any combination works, including Claude for one role (`EVALUATOR_PROVIDER=anthropic`, `EVALUATOR_MODEL=claude-opus-5`, `EVALUATOR_API_KEY=sk-ant-...`). The **System** page shows which model is in each role.

#### Checking model names

Model names change over time. To list the ones your key can use:

```bash
curl https://generativelanguage.googleapis.com/v1beta/openai/models -H "Authorization: Bearer YOUR_GEMINI_KEY"
curl https://api.x.ai/v1/models -H "Authorization: Bearer YOUR_XAI_KEY"
curl https://api.anthropic.com/v1/models -H "x-api-key: YOUR_ANTHROPIC_KEY" -H "anthropic-version: 2023-06-01"
```

Any other service with an OpenAI-compatible API (Groq, OpenRouter, OpenAI) works the same way: `openai_compatible`, its base URL, a model name and your key.

### Step 4: start the app

```bash
./scripts/dev.sh
```

This starts the backend API on port 8000 and the dashboard on port 5173. Open **http://localhost:5173**. Stop both with `Ctrl+C`.

If port 8000 is already used by another program, pick another one:

```bash
BACKEND_PORT=8100 ./scripts/dev.sh
```

Open the **System** page first. Every row should say `ok`. If `llm` says `not configured`, recheck step 3 and restart `dev.sh`.

### Step 5: ask a research question

On the **Research** page, type a question such as *How does speculative decoding speed up LLM inference?* and press **Ask**. Keep **Self-improving** selected.

The first question takes one to three minutes, because the system searches arXiv, downloads and reads PDFs, and embeds them. Repeat questions on the same topic are much faster since everything is cached in `data/`.

You will see:

- the answer, with numbered citations; click a number to jump to its evidence
- each evidence chunk with its paper, section, page and its α·semantic + β·recency + γ·feedback score bar
- the self-evaluation scores with the judge's reasons
- the ranking weights that were used

Use **Inspect retrieval only** to see the ranking without calling the LLM, and switch to **Baseline** to compare.

### Step 6: give feedback and watch the system learn

Press 👍 or 👎 on the answer, or on a single evidence chunk. Then open **Improvement history**: every self-evaluation and every 👍/👎 adds a row showing how α, β and γ moved and why (the slopes). Ask related questions again and the ranking will reflect what it learned.

### Step 7: run the Baseline vs Self-Improving experiment

With the app stopped or running, in a new terminal from the project folder:

```bash
.venv/bin/python evaluation/run_experiment.py --run-id my-first-run --limit 6 --cycles 2 --test-limit 3
.venv/bin/python evaluation/plot_results.py my-first-run
```

That small run (6 questions, 2 cycles, 3 held-out paraphrases, about 24 LLM-backed queries) takes 10 to 40 minutes depending on the LLM. The full experiment drops the limits:

```bash
.venv/bin/python evaluation/run_experiment.py --run-id full-run --cycles 3 --test-limit 12
.venv/bin/python evaluation/plot_results.py full-run
```

That is 120 queries, about 1 to 2 hours depending on the provider and rate limits. Results land in `evaluation/results/<run-id>/` (`report.md`, charts, CSV) and appear on the dashboard's **Experiments** page.

Tips for long runs:

- Keep the laptop awake and the lid open. On macOS, `caffeinate -i .venv/bin/python evaluation/run_experiment.py ...` stops idle sleep.
- If it is interrupted, run the same command again: finished steps are skipped.
- Use a new `--run-id` for every fresh experiment. Each run learns from scratch.

### Run with Docker instead

Needs only [Docker Desktop](https://www.docker.com/products/docker-desktop). Do step 3 first (`cp .env.example .env`, then edit it), then:

```bash
docker compose up --build
```

Open http://localhost:5173. The first build downloads about 2 GB. Data persists in `./data`.

### Windows without Docker

In PowerShell, from the project folder:

```powershell
copy .env.example .env
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
.venv\Scripts\python scripts\download_models.py
cd frontend; npm install; cd ..
```

Then run the two servers in two terminals:

```powershell
cd backend; ..\.venv\Scripts\uvicorn app.main:app --port 8000
```

```powershell
cd frontend; npm run dev
```

### Troubleshooting

- **`Python 3.11+ is required`:** install a newer Python (step 1), then run `./scripts/setup.sh` again.
- **`llm: not configured` on the System page:** the key or base URL in `.env` is empty or misspelled. Fix it and restart `dev.sh`.
- **A question fails with `HTTP 401` or `403`:** the API key is wrong or has no credit.
- **`HTTP 404` or `model not found`:** the model name is not available to your key. List models with the `curl` commands in step 3.
- **`arXiv returned HTTP 429`:** arXiv is rate limiting you. The system waits and retries by itself; if it keeps happening, wait a few minutes.
- **The dashboard shows `Backend unreachable`:** the backend is not running, or it runs on a different port than the dashboard expects. Start both with the same `BACKEND_PORT`.
- **Answers are cut off or fail with `truncated`:** raise `LLM_MAX_TOKENS` in `.env`.
- **Errors after pulling new code:** the database schema may have changed. See below.

### Reset everything

All downloaded papers, the vector index, the database and learned weights live in `data/`. To start from zero:

```bash
rm -rf data/rag.db data/chroma data/papers data/pdfs
```

## Pipeline

```
User query
  → Query analysis            keywords for arXiv (stopword filtering)
  → Live arXiv retrieval      cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, stat.ML, recency window, local cache
  → PDF acquisition           top N papers, abstract fallback
  → Extraction + chunking     PyMuPDF, section detection, paragraph-aware chunks with overlap
  → Embeddings                sentence-transformers, stored in ChromaDB
  → Vector search             cosine similarity over this query's candidate papers
  → Hybrid ranking            α·semantic + β·recency + γ·feedback
  → Grounded generation       LLM answers only from numbered evidence, [n] citations
  → Citation mapping          every [n] mapped to a chunk; invalid markers removed and counted
  → Self-evaluation           LLM judge rates chunks, citations, coverage, relevance
  → Feedback storage          SQLite: query, chunks, scores, answer, evaluation, 👍/👎
  → Adaptive update           α, β, γ move toward what separated relevant evidence
  → Better retrieval next time
```

Everything for one question is stored in SQLite (`data/rag.db`), so any answer can be traced back to the papers, chunks, scores and weights that produced it.

## How each stage works

### 1. Query analysis and live arXiv retrieval
`backend/app/services/query_analysis.py`, `arxiv_client.py`, `paper_retrieval.py`

The question is reduced to up to five keywords (question words and generic research words are dropped). These become an arXiv API query restricted to the six AI/ML categories and a submission-date window:

```
(all:"chain of thought" AND all:llm) AND (cat:cs.AI OR ... OR cat:stat.ML) AND submittedDate:[... TO ...]
```

If the strict `AND` query returns too few papers, the system retries with `OR`. Requests are spaced at least 3 seconds apart (arXiv's guideline), retried with exponential backoff that honours `Retry-After`, and every search result is cached in the `arxiv_search_cache` table so repeated questions make no API calls. Paper metadata (title, authors, abstract, dates, categories, arXiv ID, URLs) lives in `papers`.

### 2. Full text and chunking
`pdf_fetcher.py`, `pdf_extractor.py`, `chunking.py`, `document_processor.py`

The top `PDF_MAX_PAPERS_PER_QUERY` papers have their PDFs downloaded (size-capped, checked to be a real PDF) and parsed with PyMuPDF block by block:

- **Section detection** recognises numbered (`3.2 Training Details`), roman, and named headings (`Related Work`), including headings split across lines.
- **Cleaning** joins hyphenated line breaks and drops figure/table debris (low letter ratio).
- **Bibliography removal** stops at `References`, or when blocks look like reference lists (years, initials, `arXiv preprint`, `pp.`), because reference lists match queries well but contain no findings.

Chunks never cross a section boundary, are cut at sentence boundaries up to `CHUNK_SIZE_CHARS`, and carry `CHUNK_OVERLAP_CHARS` of the previous chunk's last sentences. The abstract is always chunk 0. If the PDF is missing, unreadable or scanned, the paper is stored as `abstract_only` with the reason in `pdf_error`. Each chunk stores paper ID, section, page, source (`pdf`/`abstract`) and position.

### 3. Embeddings and vector search
`embeddings.py`, `vector_store.py`, `indexer.py`

Chunks are embedded with `sentence-transformers/all-MiniLM-L6-v2` (normalised vectors, title and section prepended to the text) and stored in a persistent ChromaDB collection using cosine distance. Search is restricted to the papers retrieved for the current question and returns `RETRIEVAL_CANDIDATE_POOL` candidates with similarity `1 - cosine distance`.

### 4. Hybrid ranking
`ranking.py`, `feedback_scores.py`, `retrieval_pipeline.py`

```
final = α · semantic + β · recency + γ · feedback        α + β + γ = 1,  each in [WEIGHT_MIN, WEIGHT_MAX]
```

- **semantic:** similarity min-max normalised over the candidate pool, so all three terms share the 0 to 1 scale.
- **recency:** `0.5 ^ (age_days / RECENCY_HALF_LIFE_DAYS)`, so a paper loses half its recency score every half-life.
- **feedback:** what past questions taught the system about this chunk (next section). Unknown chunks get the neutral 0.5.

The top `RETRIEVAL_TOP_K` chunks are selected with at most `MAX_CHUNKS_PER_PAPER` from one paper, so the answer draws on several sources. Every component score is saved per retrieved chunk.

### 5. Grounded generation and citations
`generation.py`, `citations.py`, `llm.py`

The selected chunks are numbered `[1]..[k]` with title, arXiv ID, year, section and page. The system prompt requires the model to use only these excerpts, end every factual sentence with the numbers that support it, never cite numbers that were not supplied, and set `insufficient_evidence` with a description of what is missing when the excerpts do not answer the question. Output is structured JSON validated with Pydantic.

The answer is then split into claims (sentences) and every marker is mapped to the exact chunk. Markers that point outside `[1..k]` are removed from the answer and recorded in `invalid_citations`; factual sentences without any valid citation are counted in `uncited_claims`. The system therefore never shows a citation it cannot resolve to stored evidence.

Two LLM providers are supported:
- **anthropic** (default, `claude-opus-5`): official SDK, `messages.parse` structured output, refusal handling via `stop_reason`, and server-side refusal fallbacks (`fallbacks: "default"`) enabled for models that support them.
- **openai_compatible:** any `/chat/completions` endpoint (Gemini, Grok, Groq, OpenRouter, OpenAI), JSON mode plus schema validation with one repair attempt, and a fallback without JSON mode for endpoints that reject it.

### 6. Self-evaluation
`evaluation.py`

A second LLM call acts as a strict judge. It does not output the final scores. It makes small, checkable judgments, and the scores are computed from them in code:

| metric | computed as |
|---|---|
| retrieval precision | share of top-k chunks judged `relevant` to the question |
| retrieval relevance | mean of relevant 1, partial 0.5, irrelevant 0 |
| groundedness | mean over factual claims of the best support among its citations (uncited factual claim = 0) |
| citation accuracy | mean support over every claim→chunk citation, with each invalid marker counted as 0 |
| answer relevance | judge's 0 to 4 rating divided by 4 |
| evidence coverage | share of the question's aspects that the retrieved evidence covers |

The judge's per-chunk relevance and per-citation verdicts are saved on `retrieved_chunks.judged_relevance` and `citations.support`/`verdict_reason`; the six scores, their mean and the reasoning are saved in `evaluations`. The judge can be the same model as the writer or a different model or provider (Quick start, step 3).

## The self-improvement mechanism

There are two learning loops, both driven only by stored evaluations and feedback.

**Loop 1: chunk memory (the γ term).** Each past signal about a chunk becomes evidence for its feedback score on future questions:

| signal | value | weight |
|---|---|---|
| 👍/👎 on a specific evidence chunk | 1 / 0 | 1.0 |
| 👍/👎 on the whole answer, applied to the chunks it cited | 1 / 0 | 0.5 |
| judge's relevance rating for a retrieved chunk | 1 / 0.5 / 0 | 0.5 |
| judge's support verdict when the chunk was cited | 1 / 0.5 / 0 | 0.5 |

Each signal is further weighted by how similar its original question is to the current one, `max(0, (cos - τ) / (1 - τ))` with τ = `FEEDBACK_SIMILARITY_THRESHOLD`, so feedback transfers to related questions but not to unrelated ones. The score is a Laplace-smoothed average that starts at the neutral 0.5:

```
feedback(chunk) = (prior · 0.5 + Σ wᵢ · valueᵢ) / (prior + Σ wᵢ)
```

**Loop 2: weight adaptation (α, β, γ).** After each evaluated proposed-mode answer (and after each 👍/👎), `adaptation.py` asks which ranking component actually separated the relevant chunks from the irrelevant ones in that answer's top-k. For each component it computes the regression slope of the component score on the relevance label:

```
slope_c = cov(c, relevance) / var(relevance)
```

Positive slopes are normalised into a target weight vector `w*`, and the weights take one bounded step toward it:

```
w ← (1 − η) · w + η · w*,   then projected so that Σw = 1 and every w ∈ [WEIGHT_MIN, WEIGHT_MAX]
```

`η` is `WEIGHT_LEARNING_RATE`, so no single answer can move a weight by more than η. No update happens if fewer than `ADAPTATION_MIN_LABELS` chunks are labelled, all labels are equal, or no component has a positive slope. Every update writes a row to `weight_snapshots` with the weights before and after, the slopes, the target, the learning rate and the triggering query, so the whole trajectory is auditable at `GET /api/improvement/history`.

Learning is **scoped**: weights and signals belong to either the live system or one experiment run (`experiment_run`), and only proposed-mode queries teach the system. An experiment therefore always starts from the initial weights and learns only from its own history.

## Baseline vs proposed

| | Baseline | Proposed (self-improving) |
|---|---|---|
| arXiv retrieval, PDFs, chunks, embeddings | same | same |
| ranking | semantic only (α = 1, β = γ = 0) | α·semantic + β·recency + γ·feedback |
| generation and citation mapping | same | same |
| self-evaluation | yes, to measure it | yes |
| learns from evaluation and feedback | no | yes |

Both modes share the arXiv cache, so in an experiment they see the same candidate papers and only the ranking differs.

## Experiments

`evaluation/questions.json` holds 24 AI/ML research questions, each with a paraphrase that is never seen during learning.

```bash
.venv/bin/python evaluation/run_experiment.py --run-id my-run --cycles 3 --baseline-cycles 1 --test paraphrase
.venv/bin/python evaluation/plot_results.py my-run
```

The protocol:

1. **Warm-up:** every question and paraphrase is retrieved once, so arXiv results, PDFs and embeddings are cached and both systems see identical candidates.
2. **Training cycles:** each cycle asks every question to the proposed system, which evaluates itself and adapts after every answer. The baseline answers the same questions (it does not learn, so one cycle is enough to measure it; use `--baseline-cycles` to repeat).
3. **Held-out test:** the paraphrased questions go to both systems with learning frozen (`learn=False`). This measures whether what was learned transfers to new wording rather than memorising the training questions.

`run_experiment.py` is resumable (finished steps are skipped) and exports `evaluation/results/<run>/queries.csv` and `summary.json`. `plot_results.py` turns those files into:

- `metrics_by_cycle.png`: the six metrics per cycle, proposed against the baseline.
- `weights.png`: α, β, γ for every proposed-mode query in order.
- `retrieval_change.png`: top-k overlap (Jaccard) with the previous cycle, the direct measure that retrieval behaviour changed.
- `test_comparison.png`: held-out paraphrases, baseline against proposed.
- `latency.png`: mean time per stage.
- `report.md`: the same numbers as tables, plus paired differences with 95% bootstrap intervals and win/loss counts on the held-out set.

Every number comes from stored query records. Nothing in `evaluation/results/` is written by hand. The same per-cycle aggregates are served at `GET /api/experiments/{run}/cycles` for the dashboard.

## Results

Results from the experiments that have been run, generated by `evaluation/plot_results.py`:

- [`exp-qwen7b-24q-3c`](evaluation/results/exp-qwen7b-24q-3c/report.md): 24 questions, 3 learning cycles, 12 held-out paraphrases, with qwen2.5 7B as both writer and judge. Raw data: [`queries.csv`](evaluation/results/exp-qwen7b-24q-3c/queries.csv), [`summary.json`](evaluation/results/exp-qwen7b-24q-3c/summary.json).

![Scores across feedback cycles](evaluation/results/exp-qwen7b-24q-3c/metrics_by_cycle.png)
![Ranking weights over the run](evaluation/results/exp-qwen7b-24q-3c/weights.png)
![Held-out paraphrases](evaluation/results/exp-qwen7b-24q-3c/test_comparison.png)

A 7B model is a noisy judge, so treat this run as a working demonstration of the pipeline; a run with a stronger, separate judge (Quick start, Setup 2) gives more reliable numbers.

## API

Interactive docs at http://localhost:8000/docs.

| method | path | purpose |
|---|---|---|
| POST | `/api/query` | run the full pipeline (`mode`: `baseline`/`proposed`, `learn`, `experiment_run`, `cycle`) |
| GET | `/api/query`, `/api/query/{id}` | recent queries, or one with evidence, citations, evaluation, feedback |
| POST | `/api/feedback` | 👍/👎 on an answer or one evidence chunk; triggers a weight update |
| POST | `/api/retrieve` | ranking only, with the score breakdown, no LLM |
| GET | `/api/papers/{id}` | paper metadata and chunks (`?include_chunks=true`); `POST .../process` re-extracts |
| GET | `/api/arxiv/search` | live arXiv search with caching |
| GET | `/api/metrics` | mean scores, latency and feedback per mode (`?experiment_run=`) |
| GET | `/api/improvement/history` | current weights and every weight update with its reasoning |
| GET | `/api/experiments`, `/api/experiments/{run}/cycles` | experiment runs and per-cycle comparison |
| GET | `/api/system/status` | storage, database, vector store, embedding model, LLM, counts |

## Project layout

```
backend/app/
  api/        one router per resource
  core/       settings (validated), SQLite engine, logging
  models/     SQLAlchemy tables: papers, chunks, queries, retrieved_chunks, citations,
              evaluations, feedback, weight_snapshots, arxiv_search_cache, experiment_runs
  schemas/    Pydantic request/response models
  services/   one file per pipeline stage (see above); container.py wires them together
  main.py     app factory
frontend/src/ React dashboard (components, pages, services)
evaluation/   questions.json, run_experiment.py, plot_results.py, results/
scripts/      setup.sh, dev.sh, download_models.py
tests/        pytest suite with fake arXiv, embedder and LLM; no network needed
data/         SQLite DB, Chroma index, PDFs (git-ignored)
```

## Configuration

Every setting is an environment variable (see `.env.example`), validated at startup in `backend/app/core/config.py`. The ones most worth knowing:

- **Retrieval:** `ARXIV_MAX_RESULTS`, `ARXIV_RECENCY_DAYS`, `PDF_MAX_PAPERS_PER_QUERY`, `RETRIEVAL_CANDIDATE_POOL`, `RETRIEVAL_TOP_K`, `MAX_CHUNKS_PER_PAPER`.
- **Ranking:** `ALPHA_INIT`, `BETA_INIT`, `GAMMA_INIT` (must sum to 1), `WEIGHT_MIN`, `WEIGHT_MAX`, `RECENCY_HALF_LIFE_DAYS`.
- **Learning:** `WEIGHT_LEARNING_RATE`, `ADAPTATION_MIN_LABELS`, `FEEDBACK_PRIOR_STRENGTH`, `FEEDBACK_SIMILARITY_THRESHOLD`.
- **LLM:** `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_EFFORT`, `LLM_FALLBACKS`, `EVALUATOR_MODEL`.

API keys are only read from the environment and are never returned by any endpoint.

## Testing and conventions

```bash
.venv/bin/pytest                 # 200+ tests, no network or LLM needed
(cd frontend && npm run build)
```

Commits follow Conventional Commits, enforced by `.githooks/commit-msg`, and source files contain no comments, enforced by `tests/test_code_style.py`. See `CONTRIBUTING.md`.

## Limitations

- The judge is an LLM, and by default the same model as the generator, so self-evaluation can share the generator's blind spots. Use a separate judge (Quick start, Setup 2) and read the stored reasoning rather than the numbers alone.
- Weight adaptation learns from the top-k only (chunks the system already chose), so it refines the ranking rather than discovering evidence it never retrieved.
- The training cycles repeat the same questions; the held-out paraphrase test is what shows transfer.
- arXiv keyword search is the recall ceiling: a paper the API does not return cannot be ranked.
- Section detection is heuristic and some PDFs (two-column layouts, scanned papers) fall back to coarser sections or the abstract.

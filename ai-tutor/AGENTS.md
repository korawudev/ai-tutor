# PROJECT KNOWLEDGE BASE

**Generated:** 2026-09-11
**Commit:** faee2ae
**Branch:** main

## OVERVIEW
ai-tutor: LLM-powered tutoring monorepo. 7 FastAPI microservices + shared/ library + React 18 frontend + pgvector/Redis infra. Ollama/OpenAI-compatible LLM backend via `shared/llm/router.py`.

## STRUCTURE
```
ai-tutor/
├── gateway/          # BFF: auth, runs/threads orchestration, SSE, proxies agents
├── knowledge-agent/  # doc ingest: fetch→parse→chunk→embed
├── rag-agent/        # hybrid search (BM25+vector) + rerank + query rewrite
├── quiz-agent/       # question generation + grading + wrong-question book
├── review-agent/     # SM-2 spaced repetition + review scheduling
├── progress-agent/   # mastery scoring + dashboard aggregation
├── feynman-agent/    # Feynman-technique Socratic evaluation state machine
├── shared/           # cross-service: DB engines, models, LLM router, utils
├── migrations/       # Alembic versions (shared models only)
├── web-app/          # React 18 + TS + Vite (see web-app/AGENTS.md)
└── tests/            # pytest: unit/ + integration/
```

## AGENT LAYOUT (all 7 identical)
```
<agent>/{app,tests}/
├── app/main.py       # FastAPI factory, /health + / root endpoints
├── app/api/*.py      # routers (mounted at /api/...)
├── app/services/     # business logic layer
├── app/tools/        # LLM-tool-adjacent helpers (NOT langchain tools)
├── app/core/         # config/settings
└── tests/            # per-agent smoke tests
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Auth / login / JWT / user endpoints | `gateway/app/api/auth.py` | generates JWT for agent calls |
| Cross-agent orchestration / SSE | `gateway/app/api/runs.py`, `gateway/app/core/sse_manager.py` | run lifecycle |
| LLM provider routing (DeepSeek/Qwen/GLM fallback) | `shared/llm/router.py` | keyed by env API keys |
| DB models / shared schema | `shared/models/` | ALL agents import from here |
| Alembic migrations | `migrations/versions/` | hand-written, one per change |
| SM-2 scheduling math | `review-agent/app/tools/schedule_manager.py` | mastery/interval fields |
| Vector search internals | `rag-agent/app/tools/vector_store.py` | SQLAlchemy Core, NOT ORM |
| Frontend API client | `web-app/src/services/api.ts` | axios, points at gateway |

## CODE MAP
| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| `LLMRouter.chat()` | method | `shared/llm/router.py` | ~15 | routed LLM chat across agents |
| `init_db()` | func | `shared/database.py` | 8 | async engine + session factory |
| `settings` | obj | `shared/utils/config.py` | ~12 | pydantic-settings singleton |
| `run_query()` | func | `gateway/app/api/runs.py` | core | orchestrates agent pipeline |
| `FeynmanState` | enum | `feynman-agent/app/state_machine.py` | 2 | state transitions |

## CONVENTIONS
- **Shared models only**: never define SQLAlchemy models inside an agent; import from `shared.models`
- **Lazy imports**: `app.main` imports agents' routers and `shared` modules inside functions where agents must run standalone (prevents circular/namespace collisions)
- **Naive UTC**: `datetime.utcnow()` everywhere (lint-ignored DTZ001/DTZ003, documented in pyproject)
- **Chinese comments**: domain/API comments in Chinese match codebase style
- **Ruff gates**: `ruff check` + `ruff-format` + frontend `tsc --noEmit` via pre-commit; `COM812` ignored (formatter owns trailing commas)
- **Per-file ignores**: tests allow S101/SLF001/S105; api modules allow ARG001/ARG002/S110; config allows S105

## ANTI-PATTERNS (THIS PROJECT)
- **NEVER** add a new root package name for an agent's app (`app`) — tests do namespace-switching via `sys.modules`; container copies agent dir so `app` stays unprefixed
- **NEVER** use `os.path.join` in tests for paths — use `Path` (PTH rules)
- **NEVER** put `# noqa` on LLM prompt strings — wrap with `\` continuation instead (byte-identical prompt matters)
- **NEVER** compare booleans with `==`/`!=` — use `is`/`is not`
- **NEVER** write ORM queries in `rag-agent` tools — SQLAlchemy Core only (S608-sensitive user input)
- **NEVER** use md5 for content hashing — blake2b (S324)

## COMMANDS
```bash
# lint + format gate
pre-commit run --all-files
# backend unit tests (requires .venv)
make test          # pytest tests/unit
make test-all      # pytest tests/ (needs redis at localhost)
# frontend
cd web-app && npm run dev        # vite dev server
cd web-app && npx tsc --noEmit   # typecheck
# infra
docker compose up -d postgres redis
# full deploy
make build && make deploy
```

## NOTES
- Local pytest collection fails without `redis` running (integration imports); unit suite is CI-safe
- `make lint` also py_compiles `gateway/app/api/{runs,feynman}.py` (deliberate runtime-name check for lazy imports)
- First commit `2f98969`; P1 lint-gate commit `faee2ae`
# web-app AGENTS.md

**Parent:** ../AGENTS.md

## OVERVIEW
React 18 + TypeScript + Vite SPA - the ai-tutor frontend. Talks ONLY to `gateway` (port 8000); never directly to agent services.

## STRUCTURE
```
src/
├── pages/        # route-level views (Chat, Dashboard, Documents, Login, Progress, Quiz, Review, WrongBook)
├── components/   # Layout, Navbar, common/Toast, per-domain components
├── services/api.ts   # single axios instance → gateway
├── stores/authStore.ts  # zustand auth store (JWT in localStorage)
└── types/
    ├── index.ts   # facade: re-exports generated.ts + frontend-only composites
    └── generated.ts # AUTO-GENERATED from shared/models Pydantic (openapi-typescript) - DO NOT EDIT
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add API call | `src/services/api.ts` | axios, baseURL from env, /api proxy in dev |
| Auth state | `src/stores/authStore.ts` | zustand, JWT persistence |
| New page | `src/pages/` + route in `src/App.tsx` | react-router-dom v6 |
| API type shape | `src/types/generated.ts` | regenerated from backend Pydantic, see COMMANDS |
| Frontend composite types | `src/types/index.ts` | ReviewBatch/VerifyItem/BatchStats/DashboardData etc. |

## CONVENTIONS
- Strict TS: `noUnusedLocals`/`noUnusedParameters` enabled - dead code fails `tsc`
- Dev proxy: Vite forwards `/api` → `http://localhost:8000` (gateway)
- Tailwind for styling, lucide-react for icons

## ANTI-PATTERNS
- **NEVER** import from agent services or call them directly - always go through gateway

## COMMANDS
```bash
npm run dev      # vite dev server (port 3000)
npm run build    # tsc && vite build
npx tsc --noEmit # typecheck (pre-commit gate)

# regenerate API types from backend Pydantic schemas (run from repo root ai-tutor/)
.venv/bin/python scripts/export_openapi.py > /tmp/schemas.json
cd web-app && npm run gen:types   # openapi-typescript /tmp/schemas.json -o src/types/generated.ts
```

## TYPE REGENERATION (Pydantic → TS)
1. Edit/add a Pydantic model in `shared/models/` — it's exported automatically (modules listed in `shared/models/__init__.py`)
2. `.venv/bin/python scripts/export_openapi.py > /tmp/schemas.json` — verify all models appear
3. `cd web-app && npm run gen:types` — regenerates `src/types/generated.ts`
4. `npx tsc --noEmit` — if a frontend consumer breaks, the facade in `types/index.ts` (or the consumer) must be updated
5. `generated.ts` is committed — never edit it by hand

Dict-heavy frontend refinements (e.g. `QuizQuestion.options`, `mastery_change`, `SessionSnapshot` queues) live in the facade `types/index.ts` via `Omit<Schemas['X'], ...>` — regenerate + tsc catches drift.
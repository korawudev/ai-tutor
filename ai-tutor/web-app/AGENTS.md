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
└── types/index.ts # shared TS interfaces mirroring gateway schemas
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add API call | `src/services/api.ts` | axios, baseURL from env, /api proxy in dev |
| Auth state | `src/stores/authStore.ts` | zustand, JWT persistence |
| New page | `src/pages/` + route in `src/App.tsx` | react-router-dom v6 |

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
```
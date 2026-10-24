# STING Frontend

Mission Control & Investigation UI for the STING Autonomous Threat Intelligence Platform.

## Tech Stack
- **Framework:** Next.js 16 (App Router) + React 19 + TypeScript
- **Styling:** Vanilla Cyber HUD Design System (`app/globals.css`)
- **Motion & Scroll:** Lenis smooth scroll + Motion.dev (Framer Motion)
- **Visuals:** Cytoscape.js (Syndicate Graph), Lucide icons, Canvas Confetti

## Getting Started
```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the application.

## API Contract Alignment
All components build against `shared/api-schema.json` and static mocks in `shared/mocks/`.

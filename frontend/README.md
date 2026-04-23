# NeuroScout AI — Frontend

React 19 interface for the NeuroScout AI research agent.

> For the full project overview, architecture, and deployment guide, see the [Root README](../README.md).

---

## Quick Start

```bash
npm install
echo "REACT_APP_BACKEND_URL=http://localhost:8000" > .env
npm start
```

App runs on `http://localhost:3000`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `REACT_APP_BACKEND_URL` | ✅ | Full URL of the NeuroScout backend API |

---

## Tech Stack

| Package | Purpose |
|---|---|
| `react` 19 | UI framework |
| `framer-motion` | Animations & transitions |
| `react-markdown` + `remark-gfm` | Markdown rendering in report sections |
| `lucide-react` | Icon library |
| `tailwindcss` | Utility-first styling |
| `@radix-ui/*` | Accessible UI primitives |

---

## Source Structure

```
src/
├── components/
│   ├── AgentStream.jsx   # Live SSE step renderer (plan / search / reason / synth)
│   ├── QueryInput.jsx    # Research query form
│   ├── ReportView.jsx    # Structured report: summary, sections, key takeaways, refs
│   └── Sidebar.jsx       # Session history panel
├── pages/
│   └── Dashboard.jsx     # Main layout
├── lib/
│   ├── api.js            # API client & SSE helpers
│   ├── export.js         # .md / .txt export utilities
│   └── utils.js
├── hooks/                # Custom React hooks
├── index.css             # Global design tokens & component styles
└── App.js
```

---

## Scripts

| Command | Description |
|---|---|
| `npm start` | Start development server on port 3000 |
| `npm test` | Run tests |
| `npm run build` | Build production bundle to `build/` |

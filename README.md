<div align="center">

<h1>🧠 NeuroScout AI</h1>

<p><strong>Autonomous deep-research agent powered by Gemini & real-time web intelligence</strong></p>

<p>
  <a href="#-features">Features</a> ·
  <a href="#-architecture">Architecture</a> ·
  <a href="#-getting-started">Getting Started</a> ·
  <a href="#-environment-variables">Environment Variables</a> ·
  <a href="#-deployment">Deployment</a> ·
  <a href="#-api-reference">API Reference</a> ·
  <a href="#-contributing">Contributing</a>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/Gemini-3.1%20Pro-4285F4?style=flat-square&logo=google&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/MongoDB-Motor-47A248?style=flat-square&logo=mongodb&logoColor=white" alt="MongoDB" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License" />
</p>

</div>

---

## Overview

**NeuroScout AI** is a production-ready, autonomous research agent that breaks down any complex query, searches the live web, reads source pages, reasons over the evidence, and synthesises a fully-cited, structured research report — all streamed to the browser in real time.

It uses a **ReAct-style agent loop** (Plan → Search → Fetch → Reason → Synthesise) built on Google Gemini, with DuckDuckGo as the search backbone and Server-Sent Events (SSE) for live streaming.

> **Example query:** *"a person who is scared of driving"*
> NeuroScout will decompose this into clinical sub-questions, retrieve evidence from medical and research sources, and return a structured report with an Executive Summary, 3–6 evidence-based sections, inline citations, a Key Takeaways block, and a full reference list.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Autonomous ReAct Loop** | Plan → Search → Browse → Reason → Synthesise without human prompting |
| **Real-Time Streaming** | Agent steps are pushed live via SSE; the UI updates as evidence is collected |
| **Key Takeaways** | Every report ends with 3–5 punchy, actionable conclusions |
| **Inline Citations** | Every factual claim is linked to its source with clickable `[n]` badges |
| **Multi-Source Fusion** | Fetches and cross-checks up to 20 web pages per query |
| **Session Persistence** | Reports are stored in MongoDB for history and retrieval |
| **Export** | Download any report as `.md` or `.txt` with one click |
| **Sufficiency Reasoning** | Agent self-evaluates evidence gaps and runs additional searches when needed |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (React 19)                        │
│  QueryInput → AgentStream (SSE) → ReportView + KeyTakeaways     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────────┐
│                  FastAPI Backend (Python 3.9+)                   │
│                                                                  │
│  POST /api/research/stream  ──►  agent.py                        │
│                                   │                              │
│          ┌────────────────────────┼──────────────────────────┐   │
│          │        ReAct Loop      │                          │   │
│          │  1. PLAN   ──► Gemini (decompose query)           │   │
│          │  2. SEARCH ──► DuckDuckGo (ddgs)                  │   │
│          │  3. FETCH  ──► httpx + BeautifulSoup              │   │
│          │  4. REASON ──► Gemini (sufficiency check)         │   │
│          │  5. SYNTH  ──► Gemini (structured JSON report)    │   │
│          └──────────────────────────────────────────────────┘   │
│                                                                  │
│  GET  /api/sessions         ──►  MongoDB (Motor async)           │
│  GET  /api/sessions/:id     ──►  MongoDB (Motor async)           │
└──────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Google Gemini 3.1 Pro Preview (`google-genai`) |
| **Web Search** | DuckDuckGo (`ddgs`) — no API key required |
| **Backend Framework** | FastAPI + Uvicorn / Gunicorn |
| **Async HTTP** | `httpx` |
| **HTML Parsing** | `beautifulsoup4` + `lxml` |
| **Database** | MongoDB via `motor` (async) |
| **Frontend** | React 19, Framer Motion, Lucide React, Tailwind CSS |
| **Streaming** | Server-Sent Events (SSE) |
| **Deployment** | Render (backend) · Vercel (frontend) |

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.9 or higher
- **Node.js** 18 or higher & npm 9+
- **MongoDB** — [Atlas free tier](https://www.mongodb.com/cloud/atlas) or local instance
- **Google Gemini API Key** — [Get one here](https://aistudio.google.com/app/apikey)

---

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/neuroscout-ai.git
cd neuroscout-ai
```

---

### 2. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (see section below)
cp .env.example .env
# Edit .env with your keys

# Start the development server
uvicorn server:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment variables
echo "REACT_APP_BACKEND_URL=http://localhost:8000" > .env

# Start the development server
npm start
```

The app will be available at `http://localhost:3000`.

---

## 🔧 Environment Variables

### Backend — `backend/.env`

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ | — | Google Gemini API key |
| `GEMINI_MODEL` | ❌ | `gemini-3-flash-preview` | Gemini model to use for all agent steps |
| `MONGO_URL` | ✅ | — | MongoDB connection string (Atlas or local) |
| `DB_NAME` | ❌ | `neuroscout_db` | MongoDB database name |
| `CORS_ORIGINS` | ✅ | — | Comma-separated allowed origins (e.g. `http://localhost:3000`) |

**Example `backend/.env`:**

```env
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-3-flash-preview
MONGO_URL=mongodb+srv://<user>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority
DB_NAME=neuroscout_db
CORS_ORIGINS=http://localhost:3000,https://neuroscout.vercel.app
```

### Frontend — `frontend/.env`

| Variable | Required | Default | Description |
|---|---|---|---|
| `REACT_APP_BACKEND_URL` | ✅ | — | Full URL of the backend API |

```env
REACT_APP_BACKEND_URL=http://localhost:8000
```

---

## 📁 Project Structure

```
neuroscout-ai/
├── backend/
│   ├── agent.py          # ReAct agent loop — Plan/Search/Fetch/Reason/Synthesise
│   ├── server.py         # FastAPI app, SSE endpoint, session CRUD
│   ├── requirements.txt  # Python dependencies (pinned)
│   ├── Procfile          # Render/Heroku start command
│   └── tests/            # Backend unit & integration tests
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AgentStream.jsx   # Live SSE step renderer
│   │   │   ├── QueryInput.jsx    # Search input + controls
│   │   │   ├── ReportView.jsx    # Structured report + Key Takeaways
│   │   │   └── Sidebar.jsx       # Session history
│   │   ├── pages/
│   │   │   └── Dashboard.jsx     # Main application layout
│   │   ├── lib/
│   │   │   ├── api.js            # API client & SSE helpers
│   │   │   ├── export.js         # .md / .txt export utilities
│   │   │   └── utils.js          # Shared utilities
│   │   ├── hooks/                # Custom React hooks
│   │   ├── index.css             # Global styles & design tokens
│   │   └── App.js
│   └── vercel.json               # Vercel SPA rewrite rules
│
├── tests/                        # End-to-end tests
├── design_guidelines.json        # UI design system spec
└── README.md
```

---

## 🌐 API Reference

### `POST /api/research/stream`

Runs the research agent and streams events as Server-Sent Events.

**Request Body:**

```json
{
  "query": "a person who is scared of driving",
  "max_iterations": 5
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `query` | `string` | — | The research topic or question |
| `max_iterations` | `integer` | `5` | Max search iterations (clamped to 3–8) |

**Streamed Event Types:**

| `type` | Description |
|---|---|
| `start` | Session initialised |
| `plan` | Sub-questions decomposed |
| `search` | DuckDuckGo results returned |
| `observe` | Web pages fetched and parsed |
| `reason` | Evidence sufficiency evaluated |
| `synthesize` | Report being generated |
| `final` | Full report payload |
| `error` | Agent encountered a fatal error |

**Final event payload (`type: "final"`):**

```json
{
  "type": "final",
  "report": {
    "report_id": "uuid",
    "query": "...",
    "executive_summary": "...",
    "sections": [
      { "heading": "...", "content": "...", "source_ids": [1, 2] }
    ],
    "key_takeaways": ["...", "...", "..."],
    "references": [
      { "id": 1, "title": "...", "url": "...", "accessed_date": "..." }
    ],
    "search_iterations": 4,
    "generation_time_sec": 18.42,
    "created_at": "2026-04-23T16:24:21Z"
  }
}
```

---

### `GET /api/sessions`

Returns a list of all stored research sessions.

### `GET /api/sessions/{session_id}`

Returns a single session by ID.

---

## 🚢 Deployment

### Backend → Render

1. Create a new **Web Service** on [Render](https://render.com)
2. Connect your GitHub repository
3. Set **Root Directory** to `backend`
4. Set **Build Command** to:
   ```bash
   pip install -r requirements.txt
   ```
5. Set **Start Command** to:
   ```bash
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app --bind 0.0.0.0:$PORT
   ```
6. Add the following **Environment Variables** in Render dashboard:

   | Key | Value |
   |---|---|
   | `GEMINI_API_KEY` | Your Gemini API key |
   | `MONGO_URL` | Your MongoDB Atlas connection string |
   | `DB_NAME` | `neuroscout_db` |
   | `CORS_ORIGINS` | Your Vercel frontend URL |

---

### Frontend → Vercel

1. Create a new project on [Vercel](https://vercel.com)
2. Connect your GitHub repository
3. Set **Root Directory** to `frontend`
4. Set **Framework Preset** to `Create React App`
5. Add the following **Environment Variable**:

   | Key | Value |
   |---|---|
   | `REACT_APP_BACKEND_URL` | Your Render backend URL |

6. Click **Deploy** — the `vercel.json` SPA rewrite rule handles client-side routing automatically.

---

## 🧪 Running Tests

### Backend

```bash
cd backend
pip install pytest
pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm test
```

---

## 🛠️ Development Notes

### Agent Tuning

The agent behaviour is controlled by three prompt constants in `backend/agent.py`:

| Constant | Purpose |
|---|---|
| `PLAN_SYSTEM` | Instructs Gemini how to decompose queries into sub-questions |
| `REASON_SYSTEM` | Instructs Gemini to evaluate evidence sufficiency |
| `SYNTHESIZE_SYSTEM` | Instructs Gemini to produce the final structured JSON report |

**Key limits** (adjust at the top of `agent.py`):

```python
MAX_SUBQUESTIONS       = 5     # Max sub-questions generated by PLAN step
MAX_RESULTS_PER_QUERY  = 4     # DuckDuckGo results fetched per sub-question
MAX_FETCH_CHARS        = 4000  # Characters read from each web page
MAX_ITERATIONS_DEFAULT = 5     # Default search iterations
```

### Adding a New Export Format

Add a new function to `frontend/src/lib/export.js` following the pattern of `reportToMarkdown` / `reportToText`, then wire it to a button in `ReportView.jsx`.

---

## 🤝 Contributing

Contributions are welcome. Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/my-new-feature`
3. **Commit** your changes: `git commit -m "feat: add my new feature"`
4. **Push** to the branch: `git push origin feat/my-new-feature`
5. **Open** a Pull Request

Please make sure your code passes existing tests and that new functionality is covered by tests.

### Commit Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|---|---|
| `feat:` | New features |
| `fix:` | Bug fixes |
| `docs:` | Documentation changes |
| `style:` | Formatting / CSS only |
| `refactor:` | Code restructuring |
| `test:` | Adding or updating tests |
| `chore:` | Build config, dependencies |

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](./LICENSE) for details.

---

<div align="center">
  <p>Built with ❤️ using Google Gemini, FastAPI, and React</p>
</div>

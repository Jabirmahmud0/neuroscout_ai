# NeuroScout AI

NeuroScout AI is a full-stack research assistant that turns a question into a sourced, structured report. It plans research angles with Gemini, searches the live web, extracts evidence from retrieved pages, critiques gaps and conflicts, and streams progress to a React interface while the report is being assembled.

Research sessions and completed reports are stored in MongoDB so they can be reopened or deleted from the interface. Reports can also be exported as Markdown or plain text.

## How it works

```text
Question
  -> research plan
  -> web search and page extraction
  -> evidence critique and follow-up searches
  -> synthesis and polishing
  -> quality validation and targeted repair
  -> cited report
```

The validator checks report structure, causal and cross-domain reasoning, mechanism depth, source strength, real-world examples, evidence gaps, and several behavioral-science requirements. These checks guide a repair pass when the first draft is incomplete; they are quality heuristics, not a guarantee that every generated claim is correct.

## Stack

| Area | Technology |
| --- | --- |
| Frontend | React 19, React Router, Tailwind CSS, Radix UI, Framer Motion |
| Backend | FastAPI, Uvicorn, async Python |
| LLM | Google Gemini through `google-genai` |
| Search and extraction | DDGS, HTTPX, Beautiful Soup |
| Persistence | MongoDB with Motor |
| Streaming | Server-Sent Events over a streaming `fetch` response |
| Deployment | Render backend configuration and Vercel frontend configuration |

## Prerequisites

- Python 3.11
- Node.js 18 or newer and npm
- A running MongoDB instance or MongoDB Atlas connection string
- One or more Gemini API keys

## Local setup

Clone the repository, then configure and start the backend.

### 1. Backend

From the repository root:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS or Linux, activate the environment with:

```bash
source venv/bin/activate
```

Create `backend/.env`:

```dotenv
MONGO_URL=mongodb://localhost:27017
DB_NAME=neuroscout
GEMINI_API_KEY=your_gemini_api_key
CORS_ORIGINS=http://localhost:3000
```

Then start the API:

```powershell
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

The API is available at `http://localhost:8000`, and interactive API documentation is at `http://localhost:8000/docs`.

### 2. Frontend

Open another terminal from the repository root:

```powershell
cd frontend
npm install
```

Create `frontend/.env`:

```dotenv
REACT_APP_BACKEND_URL=http://localhost:8000
```

Start the development server:

```powershell
npm start
```

Open `http://localhost:3000`.

## Configuration

### Backend variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MONGO_URL` | Yes | None | MongoDB connection string. |
| `DB_NAME` | Yes | None | Database used for research sessions. |
| `GEMINI_API_KEY` | Yes | None | Primary Gemini key. It may also contain up to three comma-separated keys. |
| `GEMINI_API_KEY_2` | No | None | Additional key used for round-robin requests and quota fallback. |
| `GEMINI_API_KEY_3` | No | None | Third key used for round-robin requests and quota fallback. |
| `GEMINI_MODEL` | No | `gemini-3-flash-preview` | Gemini model name passed to the API. |
| `CORS_ORIGINS` | No | None | Comma-separated extra browser origins. Localhost and the configured production frontend are already allowed. |

### Frontend variable

| Variable | Required | Description |
| --- | --- | --- |
| `REACT_APP_BACKEND_URL` | Yes | Backend origin without the `/api` suffix. |

Environment files and local launch scripts are ignored by Git. Never commit API keys or database credentials.

## Research modes

The interface exposes `quick`, `balanced`, and `deep` modes. The selected mode is sent to the planner and critic to influence research depth. API clients can also set `max_iterations` from 2 to 8; the frontend currently uses the backend default of 5.

## API

All application endpoints use the `/api` prefix.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health, basic run statistics, LLM configuration state, and cache counts. |
| `GET` | `/api/metrics` | In-process run, search, fetch, LLM, and cache metrics. |
| `POST` | `/api/research/stream` | Start research and receive newline-delimited SSE events. |
| `GET` | `/api/sessions` | List the 20 most recent sessions. |
| `GET` | `/api/sessions/{session_id}` | Retrieve a saved session and report. |
| `DELETE` | `/api/sessions/{session_id}` | Delete a saved session. |

Example research request:

```bash
curl -N -X POST http://localhost:8000/api/research/stream \
  -H "Content-Type: application/json" \
  -d '{"query":"Why do people procrastinate despite knowing the consequences?","mode":"balanced","max_iterations":5}'
```

The response is an SSE stream containing session, planning, search, fetch, reasoning, synthesis, final-report, error, and completion events.

## Testing

Run the backend unit tests from the repository root:

```powershell
python -m pytest backend/tests/test_agent_upgrades.py
```

The API integration suite expects the backend and MongoDB to already be running:

```powershell
python -m pytest backend/tests/test_neuroscout_api.py
```

Run frontend tests or create a production build with:

```powershell
cd frontend
npm test
npm run build
```

`backend/run_evaluation.py` runs live benchmark cases and therefore requires a configured Gemini key, internet access, and potentially several API calls:

```powershell
cd backend
python run_evaluation.py
```

## Project structure

```text
backend/
  agent.py              Research, extraction, synthesis, and validation pipeline
  server.py             FastAPI routes, SSE streaming, MongoDB sessions, and metrics
  run_evaluation.py     Live benchmark runner
  tests/                Backend unit and API integration tests
frontend/
  src/components/       Research stream, input, report, and session UI
  src/lib/              API streaming and report export helpers
  src/pages/            Dashboard page
render.yaml              Render backend service definition
```

## Deployment notes

- `render.yaml` deploys the `backend` directory with Gunicorn and Uvicorn workers. Configure the backend environment variables in Render.
- `frontend/vercel.json` provides the single-page application rewrite used by Vercel. Configure `REACT_APP_BACKEND_URL` at build time.
- Add the deployed frontend origin to `CORS_ORIGINS` if it differs from the origin already allowed in `backend/server.py`.

## Limitations

- Research depends on third-party search results, source-page availability, and Gemini output.
- Some sites block automated fetching, so a search result may not become usable evidence.
- Metrics and search/fetch caches are stored in process memory and reset when the backend restarts. With multiple Gunicorn workers, each worker has independent metrics and caches.
- Generated reports should be verified before they are used for medical, legal, financial, or other high-stakes decisions.

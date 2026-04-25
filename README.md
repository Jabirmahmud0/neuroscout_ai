<div align="center">

# 🧠 NeuroScout AI

**Most AI apps wrap an API and call it a product. This is not that.**

NeuroScout is an autonomous deep-research agent that actually *thinks*. It breaks down problems, pulls live web data, builds causal chains, validates its own conclusions against a 12-point quality gate, and repairs weak reasoning before it shows you anything.

</div>

---

## The Difference

Give it a hard question. Something with no clean answer.

> *"Why do people stay stuck in bad habits?"*

A normal AI gives you a shallow listicle: *"Fear, lack of motivation, and dopamine cycles."*

NeuroScout gives you a mechanism:

```text
present bias → immediate reward preference → repeated avoidance →
dopamine reinforcement → identity shift → long-term behavior lock-in
```

That's not an explanation. That's a structural breakdown of behavior.

---

## How It Works

Every query runs through a ruthless reasoning loop:

`PLAN → SEARCH → FETCH → REASON → SYNTHESIZE → VALIDATE → REPAIR`

It doesn't generate. It **researches**. It hits live sources, extracts evidence, builds structured arguments, then subjects its own work to a brutal validation pipeline.

### The 12-Point Quality Gate
Before a report is finalised, NeuroScout checks for:
1. **Multi-Step Causal Chains** — A → B → C → D → Outcome format present
2. **Identity Feedback Loops** — Models Identity → Behavior → Outcome → Reinforcement
3. **Behavioral Economics Enforcement** — Requires 2+ distinct biases (e.g., Loss Aversion, Sunk Cost)
4. **Real-World Grounding** — Mandatory concrete examples; no purely academic fluff
5. **Insight Simplicity** — One clear, non-obvious sentence a non-expert can understand
6. **Source Authority** — Requires ≥2 research/clinical sources, caps general blogs at 50%
7. **Escalation Patterns** — Tracks Small Avoidance → Delay → Major Self-Sabotage
8. **Human Reality Layer** — Checks for social validation, FOMO, and emotional regulation loops
9. **Mechanism Depth** — Every section must explicitly explain WHY, HOW, and WHAT effect it has
10. **Cross-Domain Synthesis** — Must explicitly connect at least 2 distinct disciplines
11. **Evidence Gap Depth** — Missing evidence is labeled with what, why, and what's needed
12. **Required Architecture** — Forces a strict Neuro / Psych / Behavioral / Cross-Domain structure

If the reasoning is weak, it repairs it. If a source is missing, it re-searches. The output is either grounded, or it keeps working.

---

## The Stack

| Layer | Technology |
|---|---|
| **LLM Reasoning** | Google Gemini (3.1 Pro/Flash) |
| **Backend Engine** | FastAPI + async Python |
| **Web Search** | DuckDuckGo API |
| **Data Scraping** | httpx + BeautifulSoup |
| **State & Memory** | MongoDB (Motor) |
| **Frontend UI** | React + Tailwind CSS |
| **Real-time Delivery** | Server-Sent Events (SSE) |

---

## Running Locally

**Requirements:** Python 3.9+, Node 18+, MongoDB, Gemini API key.

**1. Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload
```

**2. Frontend**
```bash
cd frontend
npm install && npm start
```

**3. Environment Variables**

`backend/.env`:
```env
GEMINI_API_KEY=your_key_here
MONGO_URL=mongodb://localhost:27017
DB_NAME=neuroscout_db
CORS_ORIGINS=http://localhost:3000
```

`frontend/.env`:
```env
REACT_APP_BACKEND_URL=http://localhost:8000
```

---

## API Integration

**POST** `/api/research/stream`

```json
{
  "query": "Why do people self-sabotage?",
  "max_iterations": 5
}
```

Streams back the full reasoning process via SSE: plan, search queries, fetched content, intermediate reasoning, and the final report. You can watch it think in real-time.

---

## The Honest Pitch

This project started as a question: *Why does AI sound smart but fail on hard problems?*

The answer is that generation and reasoning are fundamentally different skills. An LLM naturally wants to predict the next word; it wants to please you. To get it to reason, you have to force it to show its work, check its logic, and reject its own lazy answers.

NeuroScout is built entirely around that second skill.
# NeuroScout AI - Backend ⚙️

This is the FastAPI-powered brain of **NeuroScout AI**. It handles autonomous research orchestration, web browsing, information synthesis, and data persistence.

## 🚀 Quick Start

1. **Create Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file:
   ```env
   MONGO_URL=mongodb://localhost:27017
   DB_NAME=neuroscout
   GEMINI_API_KEY=your_api_key_here
   CORS_ORIGINS=http://localhost:3000
   ```

4. **Run the Server**:
   ```bash
   python server.py
   ```

## 🧠 Core Components

- **`server.py`**: FastAPI routes, SSE streaming implementation, and MongoDB integration.
- **`agent.py`**: The multi-agent research logic. Uses an iterative loop to search, scrape, and synthesize data.
- **`test_mongo.py`**: Utility to verify database connectivity.

## 📡 API Endpoints

- `GET /api/health`: Check system status.
- `POST /api/research/stream`: Initiate a research session (returns SSE stream).
- `GET /api/sessions`: List recent research sessions.
- `GET /api/sessions/{id}`: Fetch a detailed report for a specific session.

---

For full project documentation, including frontend setup and architecture, see the [Root README](../README.md).

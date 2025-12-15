# CRAG Real Estate (MVVM) — Streamlit + FastAPI + Qdrant + SQLite

This project follows your required flow:

**Streamlit UI (REST client) → FastAPI → CRAG → Qdrant (vectors) + SQLite (relational)**

## Quickstart (local)

### 1) Backend (FastAPI)
```bash
cd backend
python -m venv .venv
# activate venv...
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will create `backend/app.db` on first run and seed default accounts if missing:
- `master / master123`
- `admin / admin123`

(You can override with env vars: `MASTER_PASSWORD`, `ADMIN_PASSWORD`.)

### 2) Frontend (Streamlit)
```bash
cd frontend
python -m venv .venv
# activate venv...
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Frontend expects the API at `http://localhost:8000` by default.
Set `API_BASE_URL` if needed.

## User Management pages (Streamlit)
- **View Users** (read-only list)
- **Register User** (create staff user)
- **Manage Users** (update + delete; role updates are master-only)

## Notes
- Qdrant is optional during early development. If Qdrant is not configured, CRAG falls back to SQLite keyword retrieval.
- When you later connect a real embedding model + Qdrant, plug it into `backend/app/services/vector_store.py`.

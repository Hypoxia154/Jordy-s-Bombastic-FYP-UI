# CRAG Real Estate (MVVM)
**Streamlit (Frontend) + FastAPI (Backend) + Qdrant (Vector DB) + Ollama (AI)**

## 🚀 Quick Start Guide

### Prerequisites
Before running the app, ensure you have these running:
1.  **Docker Desktop** (for Qdrant database)
    - Status: **Required**
    - Run: `docker compose up -d` in this folder.
2.  **Ollama** (for AI Model)
    - Status: **Required**
    - Run: `ollama serve` (or ensure the tray app is running).
    - Model: Ensure `phi3:mini` is pulled: `ollama pull phi3:mini`.

---

### 1. Start the Backend
The backend handles the API, Database, and AI logic.

```powershell
cd backend

# 1. Create/Activate Environment (if not already done)
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install Dependencies
pip install -r requirements.txt

# 3. Create the .env file with your Gemini API key (for chart generation)
#    Get your key from: https://aistudio.google.com/
```
Create a file called `.env` inside the `backend/` folder:
```
GEMINI_API_KEY=your_api_key_here
```

```powershell
# 4. Run Server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
> **Note**: On first run, it will create `app.db` and seed default users (`master`/`master123`, `admin`/`admin123`).

---

### 2. Start the Frontend
The frontend is the web interface you interact with.

```powershell
cd frontend

# 1. Create/Activate Environment (new terminal)
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install Dependencies
pip install -r requirements.txt

# 3. Run App
streamlit run streamlit_app.py
```
> The app will open at `http://localhost:8501`.

---

## 📂 Project Structure
- **`backend/`**: FastAPI app (Logic, DB, AI).
- **`frontend/`**: Streamlit app (UI, Pages).
- **`docker-compose.yml`**: Config for Qdrant database.

## 🔑 Default Accounts
- **Master Admin**: `master` / `master123`
- **System Admin**: `admin` / `admin123`

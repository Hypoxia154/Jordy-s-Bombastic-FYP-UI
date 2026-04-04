# Real Estate CRAG System (MVVM Architecture)

## Project Overview
This repository contains the Final Year Project (FYP) implementation of a **Corrective Retrieval-Augmented Generation (CRAG)** application, specifically tailored for real estate use-cases. The system operates on an MVVM (Model-View-ViewModel) architecture and offers role-based access to a real estate knowledge base through an AI-powered conversational interface.

Users interact with the system to ask complex queries about properties, tenancy laws, and real estate data. The system utilizes Large Language Models (LLMs) alongside vector-based document retrieval to produce highly accurate, grounded answers, backed by evidence.

## System Architecture
Our technology stack is partitioned into discrete layers to enhance modularity and maintainability:
- **Frontend (View)**: Developed using `Streamlit`, offering an interactive, responsive user interface.
- **Backend (API & Logic)**: Built with `FastAPI`, handling business logic, authentication, and orchestrating the AI pipeline.
- **Vector Database**: `Qdrant` is used to index and semantically search through real estate documents.
- **AI/LLM Engine**: `Ollama` running `phi3:mini` locally for secure, on-premise inference. External integration with Gemini API is utilized for structured chart generation.
- **Relational Database**: SQLite handles structured relational data such as user accounts, Role-Based Access Control (RBAC), and persistent chat history.

## Key Features
- **AI-Powered Chat Interface**: Converse with an AI that sources strictly from uploaded administrative documents.
- **Role-Based Access Control (RBAC)**: Secure access gating mapping users to `Master`, `Admin`, and `Staff` roles.
- **Document Manager**: Upload and manage knowledge base documents with automatic chunking and vector embedding.
- **Data Visualizations**: Autonomously extracts parameters from complex queries and renders analytical charts.
- **System Metrics & Logging**: Comprehensive dashboard to evaluate AI accuracy (BLEU/ROUGE), token usage, and latency.

---

## 🛠 Prerequisites

Ensure the following environments are installed and operational on your machine prior to execution:
1. **Docker Desktop**: Required to host the Qdrant vector database container.
2. **Ollama**: Must be running locally serving the baseline AI models. 
   - Ensure the required model is pulled: `ollama pull phi3:mini`
3. **Python 3.10+**: Base interpreter for backend and frontend.

---

## 🚀 Setup & Execution Guide

### 1. Database Initialization
From the root directory, launch the Qdrant container:
```powershell
docker compose up -d
```

### 2. Backend Setup
The FastAPI server manages the logical models and connections.
```powershell
# Navigate to backend directory
cd backend

# Initialize and activate the virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

**Environment Variables**: Create a `.env` file inside the `backend/` directory:
```env
# Required for autonomous chart payload extraction
GEMINI_API_KEY=your_gemini_api_key_here
```

**Run the Backend Server**:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
> *Note: Initializing the server for the first time will automatically run database migrations and provision the default administrative accounts.*

### 3. Frontend Setup
The Streamlit interface must be run in a separate terminal.
```powershell
# Navigate to frontend directory
cd frontend

# Initialize and activate the virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt

# Launch the Application
streamlit run streamlit_app.py
```
> The application will automatically bind to `http://localhost:8501`.

---

## 🔐 Administrative Credentials

The application seeds default high-privileged accounts upon initial database generation. Do not use these in an outward-facing production instance.
- **Master Account**: `master` / `master123`
- **System Admin**: `admin` / `admin123`
- **Admin Docs Password**: `Docs123` (Used to unlock the Admin Docs portal)

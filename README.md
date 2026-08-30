# LUMINA

A Comprehensive Intelligence & Analytics Platform integrating Agent-Based Modeling (ABM), Social Network Analysis (SNA), Natural Language Processing (NLP), and Retrieval-Augmented Generation (RAG).

---

## Getting Started

### 1. Create & Activate Virtual Environment

```powershell
python -m venv lumina_env
lumina_env\Scripts\activate
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Database Setup (PostgreSQL)

```powershell
# Add PostgreSQL bin to PATH if not already present
$env:PATH += ";C:\Program Files\PostgreSQL\18\bin"
psql -U postgres -c "CREATE DATABASE lumina_db;"

# Initialize database schema & tables
python -m database.models
```

### 4. Environment Configuration

Copy the example environment file and update your credentials:
```powershell
Copy-Item .env.example .env
```

### 5. Check Database Connection

```powershell
python -c "from database.connection import get_connection; conn = get_connection(); print('Connected!' if conn else 'Failed'); conn.close() if conn else None"
```

### 6. Run the Dashboard

```powershell
streamlit run dashboard/app.py
```

# Jira Agent

An AI-powered Jira assistant with Agentic RAG. It uses a local LLM to retrieve live Jira data, search internal PDF knowledge bases, and provide grounded guidance for ticket investigation and implementation.
The agent can triage tickets, search and filter issues, create confirmation-based Jira drafts, and combine Jira issue details with relevant document knowledge to suggest solutions.

## Demo

### **Agentic RAG**
- Uses LangGraph to route requests to Jira tools, the knowledge base, or both.
- Retrieves PDF knowledge using hybrid Chroma vector search and BM25 keyword search.
- Generates grounded implementation guidance from relevant document content.
- Supports combined flows: retrieve Jira details first, then find relevant knowledge-base guidance.
- Returns a clear fallback when no relevant document guidance is found.
<img src="img\kb_search.png" alt="Jira Agent demo" width="900">

#### **Ticket Triage**
- Automatically analyze ticket descriptions and generate:
  - **Priority levels** (Low, Medium, High) based on impact and urgency
  - **User stories** from technical descriptions
  - **Acceptance criteria** for QA and engineering teams
  - **Reasoning** behind priority decisions
- Creates a proposed triage result before any Jira update is made.
<img src="img\triage_ticket.png" alt="Jira Agent demo" width="900">

#### **Ticket Management**
- Fetches Jira issue details by ticket key.
- Searches and filters Jira tickets by project, status, assignee, and resolution.
- Handles missing or inaccessible tickets with a clear response.
<img src="img\shows.png" alt="Jira Agent demo" width="900">
<img src="img\search_ticket_user.png" alt="Jira Agent demo" width="900">
<img src="img\filter_status.png" alt="Jira Agent demo" width="900">
<img src="img\invalid_jira_ticket.png" alt="Jira Agent demo" width="900">

### **Issue Creation Assistant**
- Creates a structured Jira issue draft from a natural-language request.
- Generates the summary, description, project, and work type.
- Requires user confirmation before creating the issue in Jira.
<img src="img\create_ticket.png" alt="Jira Agent demo" width="900">
<img src="img\triage_created_ticket.png" alt="Jira Agent demo" width="900">
---

## 📋 Prerequisites

- **Python** 3.13+
- **Node.js** 18+ (for frontend)
- **Ollama** installed and running locally
- **Jira Cloud** account with API token
- **uv** package manager (optional, for faster installs)

---

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/Jing-Rou/jira-agent.git
cd jira-agent
```

### 2. Backend Setup

#### Create and activate virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or source .venv/bin/activate  # macOS/Linux
```

#### Install dependencies:
```bash
pip install -e .
# or with uv:
uv pip install -e .
```

#### Run migrations:
```bash
cd jiraAgent
python manage.py migrate
```

#### Start the backend:
```bash
python manage.py runserver
```
The backend will be available at `http://localhost:8000`

### 3. Frontend Setup

#### Navigate to frontend directory:
```bash
cd frontend
npm install
```

#### Start the development server:
```bash
npm run dev
```
The frontend will be available at `http://localhost:3000`

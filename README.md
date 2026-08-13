# Jira Agent

An AI-powered assistant that automates Jira ticket triage, issue creation, and ticket management using a local LLM. Intelligently classify incoming tickets, generate user stories and acceptance criteria, and streamline your team's ticket workflow.

## Demo

![Jira Agent demo]
<img src="img\triage_ticket.png" alt="Jira Agent demo" width="900">

## ✨ Features

### **Ticket Triage**
- Automatically analyze ticket descriptions and generate:
  - **Priority levels** (Low, Medium, High) based on impact and urgency
  - **User stories** from technical descriptions
  - **Acceptance criteria** for QA and engineering teams
  - **Reasoning** behind priority decisions

### **Issue Creation Assistant**
- Help draft Jira issues with proper structure:
  - Auto-generate summaries and descriptions
  - Suggest appropriate work types (Bug, Story, Feature, Epic, Request)
  - User confirmation workflow before creating in Jira

### **Ticket Management**
- Query unresolved tickets across your project
- Add comments to existing issues
- Create issue links and relationships
- Fetch specific tickets by ID

### **Agentic RAG**
- Uses the prebuilt LangGraph ReAct loop to choose Jira tools, PDF retrieval, or both
- Combines Chroma vector retrieval with BM25 keyword retrieval
- Generates grounded answers with document names and page references
- Keeps real Jira writes behind the existing confirmation endpoint

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

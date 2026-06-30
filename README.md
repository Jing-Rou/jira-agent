# Jira Agent

An AI-powered assistant that automates Jira ticket triage, issue creation, and ticket management using a local LLM. Intelligently classify incoming tickets, generate user stories and acceptance criteria, and streamline your team's ticket workflow.

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

### **Model-Agnostic**
- Uses **Ollama** for local, private LLM inference
- **LangChain** integration for flexible prompt engineering
- **Model Context Protocol (MCP)** for extensible tool management

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                    │
│                    Chat Interface                           │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/REST
┌──────────────────────────▼──────────────────────────────────┐
│           Django REST API (DRF)                             │
│  - /triage/jira-agent/ (POST)  - Send triage requests       │
│  - /triage/get-records/ (GET)  - Fetch results              │
│  - /triage/health-check/ (GET) - Check service status       │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
    ┌────────────┐   ┌──────────┐    ┌──────────────┐
    │ LLM Model  │   │ Jira     │    │ MCP Tools    │
    │ (Ollama)   │   │ Client   │    │ & Agents     │
    │ LangChain  │   │ (Async)  │    │              │
    └────────────┘   └──────────┘    └──────────────┘
                          │
                          ▼
                    ┌──────────────┐
                    │ Jira Cloud   │
                    │ REST API     │
                    └──────────────┘
```

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

#### Create `.env` file in the root directory:
```env
# Jira Configuration
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token-here
PROJECT_KEY=SCRUM  # Your Jira project key

# LLM Configuration
LLM_BASE_URL=http://localhost:11434/api
LLM_MODEL=llama2  # Or your Ollama model

# Django
DEBUG=True
SECRET_KEY=your-secret-key-here
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
The frontend will be available at `http://localhost:5173`

### 4. Ensure Ollama is Running

```bash
ollama serve
```

By default, Ollama listens on `http://localhost:11434`

---

## 🔧 Configuration

### Jira API Token
1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Copy the token and add it to `.env` as `JIRA_API_TOKEN`

### Ollama Model Selection
Available models (pull if not already available):
```bash
ollama pull llama2
ollama pull mistral
ollama pull neural-chat
```

Update `LLM_MODEL` in `.env` to match your chosen model.

---

## 💬 Usage

### Via Web Interface

1. Open `http://localhost:5173` in your browser
2. Enter a request in the chat:
   - **Triage a ticket**: `"Triage SCRUM-5"` → Agent analyzes the ticket and returns priority, user stories, and acceptance criteria
   - **Create a draft**: `"Create an issue about slow login on mobile"` → Agent drafts the issue for your confirmation
   - **Query tickets**: `"Get all unresolved tickets"` → Returns a list of open issues

### Example Workflows

#### Triage Workflow
```
User: "Triage SCRUM-42"

Agent Response:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User Stories:
- As a customer, I want fast checkout so I can complete purchases quickly.
- As an engineer, I want performance metrics so I can identify bottlenecks.

Acceptance Criteria:
- Checkout completes in < 5 seconds
- Performance dashboard is available
- No regression in other workflows

Priority: HIGH

Reasoning: Checkout is a critical user flow, and slowness directly impacts conversion rates.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### Issue Creation Workflow
```
User: "Create an issue about API rate limiting"

Agent: [Drafts issue]

Summary: "Implement API rate limiting to prevent abuse"
Description: "Add rate limiting to public API endpoints..."
Work Type: Feature

User: [Confirms draft]

Agent: Creates issue in Jira (SCRUM-52)
```

---

## 🔌 API Endpoints

### POST `/triage/jira-agent/`
Send a triage, creation, or query request to the agent.

**Request:**
```json
{
  "request": "Triage SCRUM-5"
}
```

**Response:**
```json
{
  "type": "triage_result",
  "result": {
    "user_stories": "...",
    "acceptance_criteria": "...",
    "priority": "HIGH"
  }
}
```

### GET `/triage/get-records/`
Fetch recent triage results and records.

**Response:**
```json
{
  "result": [
    {
      "ticket_key": "SCRUM-5",
      "request": "Triage SCRUM-5",
      "response": "..."
    }
  ]
}
```

### GET `/triage/health-check/`
Check if the agent service is online.

**Response:**
```json
{
  "message": "ONLINE"
}
```

---

## 📁 Project Structure

```
jira-agent/
├── frontend/                    # React + Vite UI
│   ├── src/
│   │   ├── App.jsx             # Main chat interface
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   └── vite.config.js
│
├── jiraAgent/                   # Django backend
│   ├── manage.py
│   ├── jiraAgent/              # Project settings
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   │
│   ├── jiraToolWrapper/        # Jira integration & MCP tools
│   │   ├── jira_client.py      # Jira API client
│   │   ├── server.py           # FastMCP server
│   │   ├── tools/
│   │   │   ├── create_issue.py
│   │   │   ├── add_issue_comment.py
│   │   │   ├── get_unsolved_ticket.py
│   │   │   ├── get_issue_by_id.py
│   │   │   └── create_issue_link.py
│   │   └── logs/
│   │       └── logger.py
│   │
│   ├── model/                  # LLM integration & prompts
│   │   ├── model_generate.py   # LangChain LLM wrapper
│   │   ├── system_prompts.py   # System prompts for agent
│   │   ├── prompts.json        # Few-shot examples
│   │   └── 30_prompts.json
│   │
│   └── triage/                 # Django REST API app
│       ├── views.py            # API endpoints
│       ├── serializers.py
│       ├── models.py
│       └── urls.py
│
├── pyproject.toml              # Python dependencies
├── main.py                     # Entry point
└── README.md
```

---

## 🛠️ Development

### Running Both Services

**Terminal 1 - Backend:**
```bash
cd jiraAgent
python manage.py runserver
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Terminal 3 - Ollama:**
```bash
ollama serve
```

### Logs
Backend logs are stored in `jiraAgent/jiraToolWrapper/logs/` for debugging.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add new feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🤖 What Can the Agent Do?

| Task | Status | Example |
|------|--------|---------|
| **Triage Tickets** | ✅ | `"Triage SCRUM-5"` |
| **Create Issues** | ✅ | `"Create an issue about..."` |
| **Query Tickets** | ✅ | `"Get all unresolved tickets"` |
| **Add Comments** | ✅ | `"Add comment to SCRUM-5"` |
| **Link Issues** | ✅ | `"Link SCRUM-5 to SCRUM-6"` |
| **Generate Summaries** | ✅ | `"Summarize SCRUM-5"` |

---

## 🐛 Troubleshooting

### Ollama Connection Error
- Ensure Ollama is running: `ollama serve`
- Check `LLM_BASE_URL` in `.env` matches your Ollama installation

### Jira API Errors
- Verify `JIRA_API_TOKEN` is correct
- Confirm `JIRA_BASE_URL` is your Jira Cloud instance URL (not Server)
- Check `PROJECT_KEY` matches your Jira project

### Frontend Cannot Reach Backend
- Confirm Django is running on `http://localhost:8000`
- Check CORS settings in `jiraAgent/settings.py`

---

## 📧 Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Happy triaging! 🚀**

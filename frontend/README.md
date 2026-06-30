# Jira Agent Frontend

React UI for the Django Jira triage API.

## Run locally

Start Django first from `jiraAgent`:

```powershell
cd C:\Users\User\Documents\JR\LLM\Jira-Agent\jiraAgent
..\.venv\Scripts\python.exe manage.py runserver
```

Then start React:

```powershell
cd C:\Users\User\Documents\JR\LLM\Jira-Agent\frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173

The Vite dev server proxies `/triage/*` requests to `http://127.0.0.1:8000`, so Django does not need CORS changes for local development.

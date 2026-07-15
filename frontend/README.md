# Jira Agent Frontend

Next.js UI for the Django Jira triage API.

## Run locally

Start Django first from `jiraAgent`:

```powershell
cd C:\Users\User\Documents\JR\LLM\Jira-Agent\jiraAgent
..\.venv\Scripts\python.exe manage.py runserver
```

Then start Next.js:

```powershell
cd C:\Users\User\Documents\JR\LLM\Jira-Agent\frontend
npm install
npm run dev
```

Open http://127.0.0.1:3000

Next.js proxies `/triage/*` requests to `http://127.0.0.1:8000` by default.

For a deployed Django API, set:

```env
DJANGO_API_URL=https://your-backend.example.com
```

This keeps browser requests on the same origin. Existing direct browser calls are also supported with:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-backend.example.com
```

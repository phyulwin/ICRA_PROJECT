# ICRA Project

This repository is a starter monorepo for a full-stack AI application using:

- Frontend: Next.js, React, TypeScript
- Backend: Python, FastAPI, Pydantic
- AI: Google Gemini, Vertex AI, Google ADK
- Agent infrastructure: Vertex AI Agent Engine / Agent Runtime
- Cloud: Google Cloud Platform, Cloud Run, Cloud Storage, Firestore, Secret Manager

## Project structure

```text
ICRA_PROJECT/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py
│   └── tests/
├── frontend/
│   ├── app/
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.mjs
├── infra/
├── docs/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── .venv/
```

## Python backend setup

1. Activate the virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Run the API:
   ```powershell
   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Frontend setup

From the `frontend` folder:

```powershell
npm install
npm run dev
```

## Environment

Copy `.env.example` to `.env` and update the values for your Google Cloud project and secrets.

## Notes

This is a base scaffold intended for extension with Gemini, Vertex AI, Firestore, Secret Manager, and deployment automation for Cloud Run.

The core Python dependencies are pinned in `requirements.txt`. Optional ADK and MCP packages are left as commented entries because they may require a small compatibility review before being enabled in a production app.

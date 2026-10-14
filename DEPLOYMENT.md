# Render Deployment

Configure the Render web service with the backend repository root as its **Root Directory**.

- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `python run.py`
- Health check path: `/health`

`run.py` binds Uvicorn to `0.0.0.0` and Render's injected `PORT`. Do not set a fixed port such as `8000` in Render's Start Command; Render reports “No open ports detected” when the process exits early or listens on the wrong port.

## Environment

Set these in the Render service environment:

- `SECRET_KEY`: a newly generated private signing key.
- `DATABASE_URL`: preferably the Internal Database URL for an attached Render PostgreSQL database. Both `postgres://...` and `postgresql://...` URLs are normalized to the installed psycopg 3 driver.
- `FRONTEND_ORIGIN`: the deployed frontend origin, such as `https://your-frontend.example`.
- `GROQ_API_KEY`: optional; when configured, the chat uses Groq. Without it, chat uses database-only replies.
- `AI_MODEL`: defaults to `openai/gpt-oss-120b`; set it to a model enabled for your Groq account if needed.

SQLite is suitable for local development. On Render, its filesystem is ephemeral unless the service has a persistent disk; use PostgreSQL or explicitly mount a persistent disk before storing production uploads. The legacy table migration runs only for SQLite; PostgreSQL startup skips SQLite-specific `PRAGMA` migration statements and creates the current schema normally.

After deployment, verify `https://<your-backend-domain>/health` returns `{"status":"ok",...}` and `/docs` lists `/api/uploads/tables`.

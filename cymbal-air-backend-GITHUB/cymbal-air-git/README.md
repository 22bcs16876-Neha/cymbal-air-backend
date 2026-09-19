# Cymbal Air FastAPI Backend

FastAPI backend for the Cymbal Air / CX Agent Studio travel concierge. It exposes the REST tool endpoints used by the CX OpenAPI toolset.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs

## Docker

```bash
docker build -t cymbal-air-backend .
docker run -p 8080:8080 cymbal-air-backend
```

The app uses SQLite by default for demo purposes. Set `DATABASE_URL` to a PostgreSQL connection string for a persistent production database.

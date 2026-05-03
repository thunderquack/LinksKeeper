# LinksKeeper

Lightweight URL shortener with email/password login, optional Google OAuth, numeric public
short links, and optional private hash links.

## Local Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
flask --app linkskeeper run --debug
```

Open `http://127.0.0.1:5000`.

## Configuration

- `FLASK_SECRET_KEY`: session secret.
- `APP_BASE_URL`: public URL used when rendering short links.
- `DATABASE_URL`: defaults to local SQLite.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: enables Google OAuth when both are set.

## Link Types

- Public links use the database id: `https://your-domain.example/1`.
- Private links use a long random token at the same root: `https://your-domain.example/<hash>`.

## Production Sketch

Run behind nginx with gunicorn:

```bash
gunicorn 'linkskeeper:create_app()' --bind 127.0.0.1:8000
```

Point nginx for `your-domain.example` to `127.0.0.1:8000`.

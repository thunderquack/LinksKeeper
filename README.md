# LinksKeeper

Lightweight URL shortener with email/password login, optional Google OAuth, numeric public
short links, and optional private hash links.

## Local Setup

```powershell
python -m venv .venv
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

Run with Docker Compose:

```bash
cp .env.example .env
docker compose up -d --build
```

The app listens on `127.0.0.1:8000` if nginx is on the same host and proxies to
the compose service through the published port.

SQLite is stored in the mounted local folder:

```text
./data/linkskeeper.db
```

Inside the container this is `/data/linkskeeper.db`, so rebuilding the image does
not delete links.

For Google OAuth in production, add this redirect URI in Google Cloud Console:

```text
https://your-domain.example/auth/google/callback
```

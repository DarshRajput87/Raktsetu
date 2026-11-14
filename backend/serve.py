"""Start the API against the local database or Atlas.

    python serve.py dev                # backend/.env             local MongoDB, auto-reload
    python serve.py prod               # backend/.env.production  MongoDB Atlas, no reload
    python serve.py dev --port 8010

npm run backend-dev / npm run backend-prod call this. It prints which database
it connects to before starting, so there is no doubt which data you are changing.
Render does not use it: there the settings come from the dashboard.
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

BACKEND = Path(__file__).resolve().parent
MODES = {
    "dev": {"env_file": ".env", "reload": True, "example": ".env.example"},
    "prod": {"env_file": ".env.production", "reload": False, "example": ".env.production.example"},
}


def safe_host(uri: str) -> str:
    """The server part of a MongoDB URI, without the user name or password."""
    parts = urlsplit(uri)
    return parts.hostname or uri.split("@")[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RaktSetu API")
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    mode = MODES[args.mode]

    if not (BACKEND / mode["env_file"]).is_file():
        sys.exit(f"backend/{mode['env_file']} is missing: copy backend/{mode['example']} to it and fill it in.")
    # Set before anything imports config, and inherited by the reload worker process.
    os.environ["ENV_FILE"] = mode["env_file"]
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))

    from config import get_settings

    settings = get_settings()
    print(f"RaktSetu API ({args.mode}): {mode['env_file']} -> MongoDB {safe_host(settings.mongo_uri)}, "
          f"database '{settings.db_name}', {settings.environment}", flush=True)

    import uvicorn

    uvicorn.run("api.main:app", host=args.host, port=args.port, reload=mode["reload"], app_dir=str(BACKEND))


if __name__ == "__main__":
    main()

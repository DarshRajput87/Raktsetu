"""CORS in production: only FRONTEND_ORIGIN may call the API from a browser.

The middleware reads the settings once, when api.main is imported, so each
case runs in a fresh Python process with its own environment.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
SITE = "https://raktsetu.zorvx.shop"

PROBE = """
import json, sys
from fastapi.testclient import TestClient
from api.main import app
client = TestClient(app)  # no `with`: startup (MongoDB) is not run
origin = sys.argv[1]
pre = client.options("/search", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
get = client.get("/health", headers={"Origin": origin})
print(json.dumps({"preflight": pre.status_code,
                  "allow": pre.headers.get("access-control-allow-origin"),
                  "get_allow": get.headers.get("access-control-allow-origin")}))
"""


def probe(origin: str, environment: str) -> dict:
    env = {**os.environ, "ENVIRONMENT": environment, "FRONTEND_ORIGIN": f"{SITE},https://other.example",
           "JWT_SECRET": "x" * 40, "BACKGROUND_TASKS": "false"}
    out = subprocess.run([sys.executable, "-c", PROBE, origin], cwd=BACKEND, env=env,
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_production_allows_the_site():
    result = probe(SITE, "production")
    assert result == {"preflight": 200, "allow": SITE, "get_allow": SITE}


def test_production_allows_every_listed_origin():
    assert probe("https://other.example", "production")["allow"] == "https://other.example"


@pytest.mark.parametrize("origin", ["https://evil.example", "http://raktsetu.zorvx.shop", "http://localhost:3000"])
def test_production_refuses_other_origins(origin):
    result = probe(origin, "production")
    assert result["preflight"] == 400
    assert result["allow"] is None and result["get_allow"] is None


def test_development_also_allows_any_localhost_port():
    assert probe("http://localhost:3001", "development")["allow"] == "http://localhost:3001"

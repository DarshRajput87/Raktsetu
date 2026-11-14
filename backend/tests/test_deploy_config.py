"""Deployment files: render.yaml is valid, and no database password is committed."""

import re
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
KEY = re.compile(r"^[A-Za-z_.-][A-Za-z0-9_.-]*$")
# A connection string with a real password ("user:password@"), not a placeholder like <password>.
CREDENTIALS = re.compile(r"mongodb(\+srv)?://[^\s:/@<>\"']+:(?!<)[^\s@<>\"']+@")


def test_render_env_var_keys_are_valid_names():
    service = yaml.safe_load((REPO / "render.yaml").read_text(encoding="utf-8"))["services"][0]
    keys = [var["key"] for var in service["envVars"]]
    assert all(KEY.match(key) and key != "." for key in keys), keys
    assert "MONGO_URI" in keys
    mongo = next(var for var in service["envVars"] if var["key"] == "MONGO_URI")
    assert mongo.get("sync") is False, "MONGO_URI must be entered in the Render dashboard, not stored in the file"


def test_no_database_password_in_tracked_files():
    files = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    leaks = []
    for name in files:
        path = REPO / name
        if path.suffix in {".png", ".docx", ".ico", ".pyc"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if CREDENTIALS.search(text):
            leaks.append(name)
    assert not leaks, f"connection string with a password committed in: {leaks}"

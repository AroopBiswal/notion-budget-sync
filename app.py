"""Flask web app entry point."""
import json
import os
import tempfile
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from src.ingestion.schema_mapper import (
    CACHE_DIR,
    delete_profile,
    load_profiles,
    save_profile,
    update_profile_fields,
)

# ── DB URL storage ────────────────────────────────────────────────────────────

_DB_URLS_FILE = CACHE_DIR / "db_urls.json"
_TRANSACTIONS_DIR = Path(__file__).parent / "transactions"
_TRANSACTION_EXTS = {".csv", ".tsv", ".xlsx", ".xls", ".json"}
_ENV_FILE = Path(__file__).parent / ".env"
_ENV_KEYS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "NOTION_TOKEN", "LLM_CATEGORIZATION"]


def _read_env_file() -> dict:
    """Parse .env file into a dict, preserving all lines including comments."""
    if not _ENV_FILE.exists():
        return {}
    vals = {}
    for line in _ENV_FILE.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            vals[k.strip()] = v.strip()
    return vals


def _write_env_file(updates: dict) -> None:
    """Write updates into .env, preserving comments and existing structure."""
    lines = _ENV_FILE.read_text().splitlines() if _ENV_FILE.exists() else []
    written = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                written.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    for key, val in updates.items():
        if key not in written:
            new_lines.append(f"{key}={val}")
    _ENV_FILE.write_text("\n".join(new_lines) + "\n")


def _load_db_urls() -> dict:
    if not _DB_URLS_FILE.exists():
        return {}
    return json.loads(_DB_URLS_FILE.read_text())


def _write_db_urls(data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _DB_URLS_FILE.write_text(json.dumps(data, indent=2))
from src.main import run_pipeline
from src.notion_client import add_transactions, get_client as get_notion_client, resolve_category

# token -> {"db_id": str, "pairs": list[dict], "ts": float}
_run_cache: dict = {}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB


@app.route("/")
def index():
    return render_template("index.html")


# ── Profile management ────────────────────────────────────────────────────────

@app.route("/api/profiles")
def list_profiles():
    profiles = load_profiles()
    return jsonify([
        {
            "name": name,
            "headers_preview": p.get("headers_preview", []),
            "saved": p.get("saved"),
            "date_col": p.get("date_col"),
            "merchant_col": p.get("merchant_col"),
            "amount_col": p.get("amount_col"),
            "amount_sign": p.get("amount_sign"),
        }
        for name, p in profiles.items()
    ])


@app.route("/api/profiles/<path:name>", methods=["DELETE"])
def remove_profile(name: str):
    ok = delete_profile(name)
    return jsonify({"ok": ok})


@app.route("/api/profiles/<path:name>", methods=["PATCH"])
def patch_profile(name: str):
    data = request.json or {}
    ok = update_profile_fields(name, data)
    if not ok:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/db-urls")
def list_db_urls():
    urls = _load_db_urls()
    return jsonify([{"name": k, "url": v} for k, v in urls.items()])


@app.route("/api/db-urls", methods=["POST"])
def add_db_url():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()
    if not name or not url:
        return jsonify({"error": "name and url required"}), 400
    urls = _load_db_urls()
    urls[name] = url
    _write_db_urls(urls)
    return jsonify({"ok": True})


@app.route("/api/db-urls/<path:name>", methods=["DELETE"])
def remove_db_url(name: str):
    urls = _load_db_urls()
    if name not in urls:
        return jsonify({"ok": False}), 404
    del urls[name]
    _write_db_urls(urls)
    return jsonify({"ok": True})


@app.route("/api/transaction-files")
def list_transaction_files():
    if not _TRANSACTIONS_DIR.exists():
        return jsonify([])
    files = sorted(
        ({"name": f.name, "size": f.stat().st_size}
         for f in _TRANSACTIONS_DIR.iterdir()
         if f.is_file() and f.suffix.lower() in _TRANSACTION_EXTS),
        key=lambda x: x["name"],
    )
    return jsonify(files)


@app.route("/api/transaction-files/<path:filename>")
def get_transaction_file(filename: str):
    target = (_TRANSACTIONS_DIR / filename).resolve()
    if not str(target).startswith(str(_TRANSACTIONS_DIR.resolve())):
        return jsonify({"error": "Invalid path"}), 400
    if not target.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(target)


@app.route("/api/settings")
def get_settings():
    vals = _read_env_file()
    result = {}
    for key in _ENV_KEYS:
        v = vals.get(key, "")
        if key == "LLM_CATEGORIZATION":
            result[key] = v.lower() == "true"
        else:
            result[key] = {"set": bool(v), "hint": (v[:8] + "...") if len(v) > 12 else ""}
    return jsonify(result)


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.json or {}
    updates = {}
    vals = _read_env_file()
    for key in _ENV_KEYS:
        if key == "LLM_CATEGORIZATION":
            if key in data:
                updates[key] = "true" if data[key] else "false"
        else:
            new_val = (data.get(key) or "").strip()
            if new_val:
                updates[key] = new_val
            elif key in data and data[key] == "":
                updates[key] = ""
    if updates:
        _write_env_file(updates)
    return jsonify({"ok": True, "restart_required": bool(updates)})


@app.route("/api/profiles/save", methods=["POST"])
def save_profile_route():
    data = request.json or {}
    name = data.get("name", "").strip()
    mapping = data.get("mapping", {})
    headers = data.get("headers", [])
    if not name or not mapping:
        return jsonify({"error": "name and mapping are required"}), 400
    actual = save_profile(name, mapping, headers)
    return jsonify({"ok": True, "saved_as": actual})


# ── Sync ──────────────────────────────────────────────────────────────────────

@app.route("/api/sync", methods=["POST"])
def sync():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    notion_url = request.form.get("notion_url", "").strip()
    format_name = request.form.get("format_name") or None
    save_as = request.form.get("save_as") or None
    dry_run = request.form.get("dry_run", "false").lower() == "true"

    if not notion_url:
        return jsonify({"error": "Notion database URL is required"}), 400

    suffix = Path(f.filename).suffix if f.filename else ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = run_pipeline(
            file_path=tmp_path,
            database_url=notion_url,
            format_name=format_name,
            save_as=save_as,
            dry_run=dry_run,
        )
        if dry_run:
            token = str(uuid.uuid4())
            _run_cache[token] = {
                "db_id": result.pop("_db_id"),
                "pairs": result.pop("_pairs"),
                "category_map": result.pop("_category_map"),
                "ts": time.time(),
            }
            # Evict entries older than 1 hour
            cutoff = time.time() - 3600
            for k in [k for k, v in _run_cache.items() if v["ts"] < cutoff]:
                del _run_cache[k]
            result["run_token"] = token
        return jsonify({"ok": True, **result})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        os.unlink(tmp_path)


@app.route("/api/sync-confirmed", methods=["POST"])
def sync_confirmed():
    data = request.json or {}
    token = data.get("run_token", "")
    excluded = set(data.get("excluded_ids", []))
    category_overrides = data.get("category_overrides", {})  # {txn_id: cat_name}

    cached = _run_cache.pop(token, None)
    if not cached:
        return jsonify({"error": "Session expired or not found. Please run again."}), 400

    pairs = []
    for p in cached["pairs"]:
        txn_id = p["txn"]["id"]
        if txn_id in excluded:
            continue
        cat_page_id = p["cat_page_id"]
        if txn_id in category_overrides:
            new_pid = resolve_category(category_overrides[txn_id], cached["category_map"])
            if new_pid:
                cat_page_id = new_pid
        pairs.append({"txn": p["txn"], "cat_page_id": cat_page_id})

    total = len(cached["pairs"])

    if not pairs:
        return jsonify({"ok": True, "read": total, "normalized": total,
                        "new": 0, "skipped": 0, "written": 0, "capped": False,
                        "preview": [], "is_new_format": False})

    try:
        notion = get_notion_client()
        written = add_transactions(
            notion, cached["db_id"],
            [p["txn"] for p in pairs],
            [p["cat_page_id"] for p in pairs],
        )
        return jsonify({"ok": True, "read": total, "normalized": total,
                        "new": written, "skipped": 0, "written": written,
                        "capped": False, "preview": [], "is_new_format": False})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port)

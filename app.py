"""Flask web app entry point."""
import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from src.ingestion.schema_mapper import (
    delete_profile,
    load_profiles,
    save_profile,
    update_profile_fields,
)
from src.main import run_pipeline

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
        return jsonify({"ok": True, **result})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port)

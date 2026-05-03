"""One-time Teller Connect helper.

Usage:
  1. Make sure TELLER_APP_ID is set in .env (get it from app.teller.io)
  2. Run: python -m scripts.link_account
  3. Open http://localhost:8000 in your browser
  4. Click "Link Account" and complete the Teller Connect flow
  5. Copy the printed TELLER_ACCESS_TOKEN and TELLER_ACCOUNT_ID into .env
     and add them as GitHub Actions secrets

You only need to do this once per linked account.
"""
import os
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

TELLER_APP_ID = os.getenv("TELLER_APP_ID", "")

app = Flask(__name__)

PAGE = """
<!doctype html>
<html><body style="font-family: system-ui; padding: 40px; max-width: 600px; margin: auto;">
<h1>Link your bank account</h1>
<p>This is a one-time setup. Click below to launch Teller Connect.</p>
<button id="link-button" style="padding: 12px 24px; font-size: 16px;">Link Account</button>
<pre id="result" style="background: #f0f0f0; padding: 20px; margin-top: 20px; white-space: pre-wrap;"></pre>
<script src="https://cdn.teller.io/connect/connect.js"></script>
<script>
const connect = TellerConnect.setup({
  applicationId: "{{ app_id }}",
  onSuccess: async function(enrollment) {
    const r = await fetch('/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(enrollment)
    });
    const accounts = enrollment.accounts || [];
    let out = 'SUCCESS!\\n\\nCopy these into your .env and GitHub secrets:\\n\\n';
    out += 'TELLER_ACCESS_TOKEN=' + enrollment.accessToken + '\\n\\n';
    if (accounts.length === 1) {
      out += 'TELLER_ACCOUNT_ID=' + accounts[0].id + '\\n';
    } else {
      out += 'Available accounts (pick one for TELLER_ACCOUNT_ID):\\n';
      accounts.forEach(a => {
        out += '  ' + a.id + '  ' + a.institution.name + ' ' + a.name + '\\n';
      });
    }
    document.getElementById('result').innerText = out;
  },
  onExit: function() {}
});
document.getElementById('link-button').onclick = function() { connect.open(); };
</script>
</body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, app_id=TELLER_APP_ID)


@app.route("/save", methods=["POST"])
def save():
    data = request.json
    print("\n" + "=" * 60)
    print("TELLER ENROLLMENT (save these in .env and GitHub secrets):")
    print(f"TELLER_ACCESS_TOKEN={data.get('accessToken')}")
    for account in data.get("accounts", []):
        print(f"TELLER_ACCOUNT_ID={account['id']}  # {account.get('institution', {}).get('name')} {account.get('name')}")
    print("=" * 60 + "\n")
    return jsonify({"ok": True})


if __name__ == "__main__":
    if not TELLER_APP_ID:
        print("ERROR: Set TELLER_APP_ID in .env first (get it from app.teller.io)")
        raise SystemExit(1)
    print("Open http://localhost:8000 in your browser")
    app.run(port=8000, debug=False)

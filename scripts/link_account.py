"""One-time Plaid Link helper.

Usage:
  1. Make sure PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV are set in .env
  2. Run: python -m scripts.link_account
  3. Open http://localhost:8000 in your browser
  4. Click "Link AMEX", complete the OAuth flow with American Express
  5. Copy the printed access_token into .env as PLAID_ACCESS_TOKEN
  6. Then add it as a GitHub Actions secret too

You only need to do this once. The access_token does not expire.
"""
from flask import Flask, request, jsonify, render_template_string

from plaid.api import plaid_api
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

from src.config import PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV

HOST_MAP = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}

config = Configuration(
    host=HOST_MAP[PLAID_ENV],
    api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
)
client = plaid_api.PlaidApi(ApiClient(config))

app = Flask(__name__)

PAGE = """
<!doctype html>
<html><body style="font-family: system-ui; padding: 40px; max-width: 600px; margin: auto;">
<h1>Link your AMEX</h1>
<p>This is a one-time setup. Click below to launch Plaid Link.</p>
<button id="link-button" style="padding: 12px 24px; font-size: 16px;">Link AMEX</button>
<pre id="result" style="background: #f0f0f0; padding: 20px; margin-top: 20px;"></pre>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<script>
async function start() {
  const r = await fetch('/create_link_token', { method: 'POST' });
  const { link_token } = await r.json();
  const handler = Plaid.create({
    token: link_token,
    onSuccess: async (public_token) => {
      const r2 = await fetch('/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ public_token })
      });
      const data = await r2.json();
      document.getElementById('result').innerText =
        'SUCCESS!\\n\\nCopy this into your .env:\\n\\nPLAID_ACCESS_TOKEN=' + data.access_token;
    },
    onExit: (err) => { if (err) console.error(err); }
  });
  handler.open();
}
document.getElementById('link-button').onclick = start;
</script>
</body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/create_link_token", methods=["POST"])
def create_link_token():
    req = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id="local-dev-user"),
        client_name="AMEX Budget Sync",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    resp = client.link_token_create(req)
    return jsonify({"link_token": resp["link_token"]})


@app.route("/exchange", methods=["POST"])
def exchange():
    public_token = request.json["public_token"]
    req = ItemPublicTokenExchangeRequest(public_token=public_token)
    resp = client.item_public_token_exchange(req)
    access_token = resp["access_token"]
    print("\n" + "=" * 60)
    print("ACCESS TOKEN (save this in .env and GitHub secrets):")
    print(access_token)
    print("=" * 60 + "\n")
    return jsonify({"access_token": access_token})


if __name__ == "__main__":
    app.run(port=8000, debug=False)

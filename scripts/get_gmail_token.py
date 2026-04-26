"""
Run this ONCE locally to get a Gmail OAuth2 refresh token for HF Spaces deployment.

Steps:
  1. Go to console.cloud.google.com → project sweet-devil-gprm
  2. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
  3. Application type: Desktop app → name it anything → Create
  4. Copy the Client ID and Client Secret shown
  5. Run:  python scripts/get_gmail_token.py

It opens a browser for you to sign in with your sender Gmail account.
Then prints the 3 secrets to add to HF Spaces.
"""

import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Run: pip install google-auth-oauthlib")
    sys.exit(1)

CLIENT_ID     = input("Paste your OAuth2 Client ID:     ").strip()
CLIENT_SECRET = input("Paste your OAuth2 Client Secret: ").strip()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0)

print("\n" + "="*60)
print("Add these 3 secrets to your HF Space (Settings → Secrets):")
print("="*60)
print(f"GMAIL_CLIENT_ID     = {CLIENT_ID}")
print(f"GMAIL_CLIENT_SECRET = {CLIENT_SECRET}")
print(f"GMAIL_REFRESH_TOKEN = {creds.refresh_token}")
print("="*60)

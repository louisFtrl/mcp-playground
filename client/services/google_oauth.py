import json
import streamlit as st
from google_auth_oauthlib.flow import Flow

# Load your client secret JSON string from Streamlit secrets
CLIENT_SECRET_JSON = st.secrets["GOOGLE_OAUTH_CREDENTIALS"]["CLIENT_SECRET_JSON"]

# Parse JSON string to dict
CLIENT_CONFIG = json.loads(CLIENT_SECRET_JSON)

# Scopes your app needs (adjust if needed)
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]

# Redirect URI must match what you set in Google Console
REDIRECT_URI = CLIENT_CONFIG["web"]["redirect_uris"][0]


def get_flow(state=None):
    """Create and return a Flow instance, optionally with state for security."""
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    if state:
        flow.state = state
    return flow


def get_authorization_url(state=None):
    """Return the authorization URL to redirect user to Google consent screen."""
    flow = get_flow(state=state)
    auth_url, state = flow.authorization_url(
        access_type="offline",  # get refresh token
        include_granted_scopes="true",
        prompt="consent",  # force consent screen every time
    )
    return auth_url, state


def fetch_token(flow, authorization_response_url):
    """Fetch OAuth tokens using the full redirect URL after user consent."""
    flow.fetch_token(authorization_response=authorization_response_url)
    credentials = flow.credentials
    return credentials

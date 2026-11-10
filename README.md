# Flask Auth0 App - The Context-Preserving Assistant

A modern Flask application featuring Auth0 authentication powered by [`auth0-server-python`](https://github.com/auth0/auth0-server-python) and **The Context-Preserving Assistant** with live weather powered by Open-Meteo.

Built for the Hackathon Challenge.

---

## Features

- **Auth0 Server SDK Integration**: Built with `auth0-server-python` using authorization code flow with PKCE (`S256`).
- **OIDC Scopes & API Access Token**: Requests `openid profile email` scopes and requests an API access token for `AUTH0_AUDIENCE`.
- **JWT RS256 Verification via JWKS**: Protected `/api/settings` route verifies Bearer access tokens against the Auth0 tenant's JWKS.
- **Per-User In-Memory Settings**: Users can configure their home city and temperature units (`celsius` or `fahrenheit`) on `/settings`.
- **The Context-Preserving Assistant**: Interactive `/chat` page where asking about the weather:
  1. Retrieves the user's access token from the active session.
  2. Calls `/api/settings` with `Authorization: Bearer <token>`.
  3. Geocodes the user's home city via Open-Meteo.
  4. Fetches live forecast and replies with localized temperature (e.g., *"Your home city is London, it's 6.0°C there."*).
- **Clean UI**: Responsive styling with modern cards, badge indicators, settings forms, and real-time chat interface.

---

## Project Structure

```
auth0-flask-app/
├── app.py                 # Flask app routes (/, /login, /callback, /profile, /settings, /api/settings, /chat, /logout)
├── auth.py                # Auth0 ServerClient, in-memory stores, and JWT RS256 JWKS validator
├── requirements.txt       # Dependencies (auth0-server-python, flask[async], python-dotenv)
├── static/
│   └── style.css          # Clean CSS styling for cards, forms, navigation, and chat
├── templates/
│   ├── index.html         # Landing page (login button / welcome dashboard)
│   ├── profile.html       # Protected user profile page
│   ├── settings.html      # Protected preferences page (home city & units)
│   └── chat.html          # Context-Preserving Assistant chat interface
├── .env.example           # Example environment configuration with AUTH0_AUDIENCE
├── .gitignore             # Git ignore rules (.env, venv, pycache)
└── README.md              # Project setup and documentation
```

---

## Setup & Installation

### 1. Prerequisites

- Python 3.10 or later
- An [Auth0 Account](https://auth0.com/)

### 2. Configure Auth0 Dashboard

#### A. Configure Application
1. In the **Auth0 Dashboard**, go to **Applications** > **Applications** > **Create Application**.
2. Select **Regular Web Applications**.
3. Under **Settings**, configure the following URLs:
   - **Allowed Callback URLs**: `http://localhost:5000/callback`
   - **Allowed Logout URLs**: `http://localhost:5000/`
   - **Allowed Web Origins**: `http://localhost:5000`
4. Click **Save Changes**.
5. Copy your **Domain**, **Client ID**, and **Client Secret**.

#### B. Configure API Audience
1. In the **Auth0 Dashboard**, go to **Applications** > **APIs** > **Create API**.
2. Enter a **Name** (e.g. `Assistant Settings API`) and an **Identifier** (e.g. `https://assistant-api/` or your custom audience).
3. Set the signing algorithm to **RS256**.
4. Copy the **Identifier** (this is your `AUTH0_AUDIENCE`).

### 3. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your Auth0 credentials:

```ini
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret
AUTH0_SECRET=your_32_character_session_secret_key_here
AUTH0_REDIRECT_URI=http://localhost:5000/callback
AUTH0_AUDIENCE=https://your-api-identifier/
```

> **Note**: `AUTH0_SECRET` is used for cookie encryption and must be a secure random string (at least 32 characters).

### 4. Virtual Environment & Dependencies

Activate the virtual environment:

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

Install the required packages:
```bash
pip install -r requirements.txt
```

---

## Running the Application

Start the Flask server on port `5000`:

```bash
python app.py
```

Open your browser at:
[http://localhost:5000](http://localhost:5000)

---

## Application Routes

| Route | Method | Access | Description |
|---|---|---|---|
| `/` | `GET` | Public | Home landing page. Shows login button when unauthenticated, or welcome greeting + links when logged in. |
| `/login` | `GET` | Public | Generates PKCE parameters, requests `AUTH0_AUDIENCE`, and redirects user to Auth0. |
| `/callback` | `GET` | Public | Auth0 redirect destination. Exchanges code for tokens (ID token & access token) and persists session. |
| `/profile` | `GET` | **Protected** | Displays user's name, email, avatar, and raw claims. |
| `/settings` | `GET`, `POST` | **Protected** | UI page to view and update home city and preferred temperature units. |
| `/api/settings` | `GET`, `POST` | **Protected (Bearer Token)** | API endpoint that validates the Auth0 access token (JWT, RS256, tenant JWKS) and returns/updates settings. |
| `/chat` | `GET`, `POST` | **Protected** | The Context-Preserving Assistant chat UI. Queries `/api/settings` with access token, geocodes home city, and returns live Open-Meteo weather. |
| `/logout` | `GET` | Public / Protected | Clears local session and redirects user to Auth0 logout endpoint. |

---

## Security Notes

- **Never Commit Secrets**: The `.gitignore` file excludes `.env` and local credentials. Keep production secrets in a secrets manager or deployment environment variables.
- **RS256 JWKS Token Validation**: The `/api/settings` endpoint validates JWT signatures against Auth0's public JWKS endpoint with issuer and audience verification.
- **Production Stores**: For production deployments, replace the in-memory stores with a distributed cache like Redis.

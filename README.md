# Flask Auth0 App - The Privacy-Aware RAG Bot & Assistant

A modern Flask application featuring Auth0 authentication, API token validation, **The Context-Preserving Assistant** (Open-Meteo), and **The Privacy-Aware RAG Bot** powered by **Auth0 Fine-Grained Authorization (FGA)**.

Built for the Hackathon Challenge.

---

## Features

- **Auth0 Server SDK Integration**: Built with `auth0-server-python` using authorization code flow with PKCE (`S256`).
- **OIDC Scopes & API Access Token**: Requests `openid profile email` scopes and requests an API access token for `AUTH0_AUDIENCE`.
- **JWT RS256 Verification via JWKS**: Protected `/api/settings` route verifies Bearer access tokens against the Auth0 tenant's JWKS.
- **The Context-Preserving Assistant**: Interactive `/chat` page where asking about the weather retrieves user home city via `/api/settings` and queries Open-Meteo for live localized conditions.
- **The Privacy-Aware RAG Bot (`/rag`)**:
  - Contains a dataset of internal enterprise documents (`salary_report`, `holiday_policy`, `legal_memo`, `remote_work_guide`, `security_protocol`, `financial_audit`).
  - Matches candidate documents via keyword search.
  - **Auth0 FGA Check**: Before returning any document, evaluates `FGA Check(user:<email>, viewer, document:<id>)` using the official `openfga-sdk`.
  - **Enforces Access Control**: Strictly drops denied documents. If all matching documents are denied, replies with *"You don't have access to that document."* and an *"Access denied by FGA"* note.
  - **Decision Transparency**: Displays the logged-in email and real-time allowed/denied FGA decision badges for each document in the UI.

---

## Auth0 FGA Authorization Model

```
model
  schema 1.1

type user

type role
  relations
    define member: [user]

type document
  relations
    define viewer: [role#member]
```

- **User Identifier**: The authenticated user's email, formatted as `user:<email>` (e.g. `user:employee@test.com`, `user:kusumaranikusumarani3232@gmail.com`).
- **Permissions**:
  - `document:holiday_policy`: Viewable by `role:employee#member` and `role:manager#member`.
  - `document:salary_report`: Viewable only by `role:manager#member`.
  - `document:legal_memo`: Restricted.

---

## Project Structure

```
auth0-flask-app/
├── app.py                 # Flask app routes (/, /login, /callback, /profile, /settings, /api/settings, /chat, /rag, /logout)
├── auth.py                # Auth0 ServerClient, in-memory stores, and JWT RS256 JWKS validator
├── fga.py                 # Auth0 FGA client, document dataset, keyword search & Privacy-Aware RAG pipeline
├── requirements.txt       # Dependencies (auth0-server-python, flask[async], python-dotenv, openfga-sdk)
├── static/
│   └── style.css          # Clean CSS styling for cards, forms, navigation, chat, and FGA inspector
├── templates/
│   ├── index.html         # Landing page (login button / welcome dashboard)
│   ├── profile.html       # Protected user profile page
│   ├── settings.html      # Protected preferences page (home city & units)
│   ├── chat.html          # Context-Preserving Assistant chat interface
│   └── rag.html           # The Privacy-Aware RAG Bot interface
├── .env.example           # Example environment configuration with Auth0 & FGA placeholders
├── .gitignore             # Git ignore rules (.env, venv, pycache)
└── README.md              # Project setup and documentation
```

---

## Setup & Installation

### 1. Prerequisites

- Python 3.10 or later
- An [Auth0 Account](https://auth0.com/)
- An [Auth0 FGA Account / Store](https://fga.dev/)

### 2. Configure Auth0 Dashboard

#### A. Regular Web Application
1. In the **Auth0 Dashboard**, go to **Applications** > **Applications** > **Create Application** (**Regular Web Application**).
2. Set URLs:
   - **Allowed Callback URLs**: `http://localhost:5000/callback`
   - **Allowed Logout URLs**: `http://localhost:5000/`
   - **Allowed Web Origins**: `http://localhost:5000`
3. Save and copy **Domain**, **Client ID**, and **Client Secret**.

#### B. API Audience (for `/api/settings`)
1. In **Applications** > **APIs** > **Create API**.
2. Set Identifier (e.g. `https://assistant-api/`). This is your `AUTH0_AUDIENCE`.

#### C. Auth0 FGA Store
1. In **Auth0 FGA Dashboard**, create a store and model with types `user`, `role`, `document`.
2. Generate API Credentials under Store Settings (Client ID, Client Secret).

### 3. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Configure `.env` with your Auth0 and FGA credentials:

```ini
# Auth0 Application Settings
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret
AUTH0_SECRET=your_32_character_session_secret_key_here
AUTH0_REDIRECT_URI=http://localhost:5000/callback
AUTH0_AUDIENCE=https://your-api-identifier/

# Auth0 FGA Settings
FGA_API_URL=https://api.us1.fga.dev
FGA_STORE_ID=your_fga_store_id
FGA_CLIENT_ID=your_fga_client_id
FGA_CLIENT_SECRET=your_fga_client_secret
FGA_API_TOKEN_ISSUER=auth.fga.dev
FGA_API_AUDIENCE=https://api.us1.fga.dev/
```

### 4. Install Dependencies

Activate your virtual environment and install packages:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Running the Application

Start the Flask application on port `5000`:

```bash
python app.py
```

Open your browser at [http://localhost:5000](http://localhost:5000).

---

## Application Routes

| Route | Method | Access | Description |
|---|---|---|---|
| `/` | `GET` | Public | Landing page with login button or AI feature navigation. |
| `/login` | `GET` | Public | Generates PKCE parameters, requests `AUTH0_AUDIENCE`, and redirects user to Auth0. |
| `/callback` | `GET` | Public | Handles redirect, persists ID and access tokens into the session. |
| `/rag` | `GET`, `POST` | **Protected** | **The Privacy-Aware RAG Bot**. Keyword search + Auth0 FGA check + decision inspector. |
| `/chat` | `GET`, `POST` | **Protected** | The Context-Preserving Assistant (reads user city via `/api/settings` and queries Open-Meteo). |
| `/settings` | `GET`, `POST` | **Protected** | User preferences page for home city and temperature units. |
| `/api/settings` | `GET`, `POST` | **Protected (Bearer Token)** | RS256 JWT-validated API for reading/writing user settings. |
| `/profile` | `GET` | **Protected** | Displays user profile claims and avatar. |
| `/logout` | `GET` | Public / Protected | Clears session and redirects to Auth0 logout endpoint. |

---

## Testing Privacy-Aware RAG

In the **RAG Bot** interface (`/rag`):
- Try asking: *"What is our holiday and leave policy?"* &rarr; **Allowed** for employee and manager roles.
- Try asking: *"Show me the executive salary report"* &rarr; **Allowed** for manager; **Denied** for employee with note *"Access denied by FGA"*.
- Switch between demo identities in the identity selector to observe real-time policy evaluation.

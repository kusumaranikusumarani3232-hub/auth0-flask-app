# Flask Auth0 Authentication App

A modern Flask application featuring Auth0 authentication powered by the [`auth0-server-python`](https://github.com/auth0/auth0-server-python) SDK.

Built for the Hackathon Challenge.

---

## Features

- **Auth0 Server SDK Integration**: Built with `auth0-server-python` using authorization code flow with PKCE (`S256`).
- **OIDC Scopes**: Requests `openid profile email` scopes to retrieve standard user claims.
- **In-Memory Store Architecture**: Custom dev-ready `StateStore` and `TransactionStore` implementations.
- **Protected Routes**: `/profile` route requires active authentication and renders user name, email, and avatar.
- **Clean UI**: Responsive styling with modern cards, badge indicators, and collapsible raw claims view.

---

## Project Structure

```
auth0-flask-app/
├── app.py                 # Flask application routes (/, /login, /callback, /profile, /logout)
├── auth.py                # Auth0 ServerClient and in-memory store implementations
├── requirements.txt       # Dependencies (auth0-server-python, flask[async], python-dotenv)
├── static/
│   └── style.css          # Clean CSS styling
├── templates/
│   ├── index.html         # Landing page (login button / welcome message)
│   └── profile.html       # Protected user profile page
├── .env.example           # Example environment configuration
├── .gitignore             # Git ignore rules (.env, venv, pycache)
└── README.md              # Project setup and documentation
```

---

## Setup & Installation

### 1. Prerequisites

- Python 3.10 or later
- An [Auth0 Account](https://auth0.com/)

### 2. Configure Auth0 Dashboard

1. In the **Auth0 Dashboard**, go to **Applications** > **Applications** > **Create Application**.
2. Select **Regular Web Applications**.
3. Under **Settings**, configure the following URLs:
   - **Allowed Callback URLs**: `http://localhost:5000/callback`
   - **Allowed Logout URLs**: `http://localhost:5000/`
   - **Allowed Web Origins**: `http://localhost:5000`
4. Click **Save Changes**.
5. Copy your **Domain**, **Client ID**, and **Client Secret**.

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
| `/` | `GET` | Public | Home landing page. Shows "Log In with Auth0" when unauthenticated, or a welcome greeting + links when logged in. |
| `/login` | `GET` | Public | Generates PKCE parameters and redirects user to the Auth0 login page. |
| `/callback` | `GET` | Public | Auth0 redirect destination. Exchanges authorization code for tokens and persists session. |
| `/profile` | `GET` | **Protected** | Requires authentication. Displays user's name, email, avatar, and OIDC claims. Redirects to `/login` if unauthenticated. |
| `/logout` | `GET` | Protected / Public | Clears local session and redirects user to Auth0 logout endpoint. |

---

## Security Notes

- **Never Commit Secrets**: The `.gitignore` file excludes `.env` and local credentials. Keep production secrets in a secrets manager or deployment environment variables.
- **Production Stores**: For production deployments, replace the in-memory stores (`InMemoryStateStore`, `InMemoryTransactionStore`) with a distributed cache like Redis or an encrypted cookie store.


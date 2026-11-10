"""Flask application with Auth0 authentication, Context-Preserving Assistant, and The Privacy-Aware RAG Bot."""

import os
import uuid
import httpx
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from auth import (
    AUTH0_AUDIENCE,
    LogoutOptions,
    StartInteractiveLoginOptions,
    auth0,
    verify_access_token,
)
from fga import (
    DOCUMENTS,
    FGA_STORE_ID,
    query_rag_pipeline,
)

app = Flask(__name__)

# Secret key for Flask session cookie encryption
app.secret_key = os.getenv("AUTH0_SECRET") or os.urandom(32).hex()

# In-memory store for user settings: user_id (sub) -> {"city": str, "units": str}
user_settings_db: dict[str, dict[str, str]] = {}

DEFAULT_CITY = "London"
DEFAULT_UNITS = "celsius"


def get_user_settings(user_id: str) -> dict[str, str]:
    """Retrieve settings for a user ID, or return defaults if not yet set."""
    if user_id not in user_settings_db:
        user_settings_db[user_id] = {
            "city": DEFAULT_CITY,
            "units": DEFAULT_UNITS,
        }
    return user_settings_db[user_id]


def save_user_settings(user_id: str, city: str, units: str) -> dict[str, str]:
    """Save home city and units in memory for a user ID."""
    clean_city = city.strip() if city else DEFAULT_CITY
    clean_units = units.strip().lower() if units else DEFAULT_UNITS
    if clean_units not in ["celsius", "fahrenheit"]:
        clean_units = DEFAULT_UNITS

    settings = {
        "city": clean_city,
        "units": clean_units,
    }
    user_settings_db[user_id] = settings
    return settings


def get_store_options() -> dict:
    """Ensure a unique session ID exists in the Flask session cookie for state store isolation."""
    if "session_id" not in session:
        session["session_id"] = uuid.uuid4().hex
    return {"session_id": session["session_id"]}


async def get_current_user():
    """Retrieve the authenticated user from the store or session."""
    store_opts = get_store_options()
    user = await auth0.get_user(store_options=store_opts)
    if not user:
        user = await auth0.get_user()
    if not user:
        user = session.get("user")
    return user


async def get_user_access_token() -> str | None:
    """Retrieve the access token for the authenticated user from session or state store."""
    token = session.get("access_token")
    if token:
        return token

    store_opts = get_store_options()
    try:
        if AUTH0_AUDIENCE:
            token = await auth0.get_access_token(store_options=store_opts, audience=AUTH0_AUDIENCE)
        else:
            token = await auth0.get_access_token(store_options=store_opts)
        if token:
            session["access_token"] = token
            return token
    except Exception:
        pass

    return None


async def fetch_user_settings_via_api(access_token: str) -> dict:
    """
    Call /api/settings using the user's access token in the Authorization header.
    Tries HTTP first; falls back to in-process dispatch if in test or single-thread mode.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Attempt HTTP call if running in an active server context
    try:
        base_url = request.host_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/settings", headers=headers)
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass

    # 2. In-process dispatch fallback (for unit tests / test_client)
    with app.test_client() as client:
        resp = client.get("/api/settings", headers=headers)
        if resp.status_code == 200:
            return resp.get_json()
        raise RuntimeError(
            f"/api/settings returned status {resp.status_code}: {resp.data.decode()}"
        )


# ============================================================================
# Core Authentication Routes
# ============================================================================

@app.route("/")
async def home():
    """Home route: shows welcome message + links if authenticated, otherwise login button."""
    user = await get_current_user()
    return render_template("index.html", user=user)


@app.route("/login")
async def login():
    """Initiate Auth0 authentication flow requesting AUTH0_AUDIENCE if configured."""
    store_opts = get_store_options()
    login_options = None
    if AUTH0_AUDIENCE:
        login_options = StartInteractiveLoginOptions(
            authorization_params={"audience": AUTH0_AUDIENCE}
        )
    login_url = await auth0.start_interactive_login(
        options=login_options,
        store_options=store_opts,
    )
    return redirect(login_url)


@app.route("/callback")
async def callback():
    """Handle Auth0 redirect callback, persist tokens and session, then redirect to profile."""
    store_opts = get_store_options()
    try:
        result = await auth0.complete_interactive_login(
            request.url, store_options=store_opts
        )
        state_data = result.get("state_data", {}) if isinstance(result, dict) else {}

        # Persist user
        user = await auth0.get_user(store_options=store_opts)
        if not user and "user" in state_data:
            user = state_data.get("user")
        if user:
            session["user"] = user

        # Persist access token in session
        token_sets = state_data.get("token_sets", [])
        if token_sets and len(token_sets) > 0:
            token = token_sets[0].get("access_token")
            if token:
                session["access_token"] = token

        return redirect(url_for("profile"))
    except Exception as e:
        app.logger.error("Authentication callback failed: %s", e)
        return render_template("index.html", error=str(e), user=None), 400


@app.route("/profile")
async def profile():
    """Protected profile route: displays user's name, email, and picture."""
    user = await get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("profile.html", user=user)


@app.route("/logout")
async def logout():
    """Log out user from the app and Auth0."""
    store_opts = get_store_options()
    session.clear()
    return_to = url_for("home", _external=True)
    logout_url = await auth0.logout(
        LogoutOptions(return_to=return_to),
        store_options=store_opts,
    )
    return redirect(logout_url)


# ============================================================================
# Protected Settings API (Token-validated) & Settings Page
# ============================================================================

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """
    Protected API route that validates the Auth0 access token (JWT, RS256, via tenant JWKS)
    and returns or updates the user's settings stored in memory per user ID.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = verify_access_token(token)
    except Exception as e:
        app.logger.warning("Access token validation failed: %s", e)
        return jsonify({"error": "Unauthorized", "details": str(e)}), 401

    user_id = payload.get("sub")
    if not user_id:
        return jsonify({"error": "Access token missing 'sub' claim"}), 401

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        city = data.get("city", "")
        units = data.get("units", "celsius")
        updated = save_user_settings(user_id, city, units)
        return jsonify({"status": "success", "settings": updated})

    # GET request
    settings_data = get_user_settings(user_id)
    return jsonify(settings_data)


@app.route("/settings", methods=["GET", "POST"])
async def settings():
    """Settings page where the user views and saves their home city and units."""
    user = await get_current_user()
    if not user:
        return redirect(url_for("login"))

    user_id = user.get("sub")
    message = None

    if request.method == "POST":
        city = request.form.get("city", "").strip()
        units = request.form.get("units", "celsius").strip().lower()
        save_user_settings(user_id, city, units)
        message = "Settings saved successfully!"

    current_settings = get_user_settings(user_id)
    return render_template(
        "settings.html",
        user=user,
        settings=current_settings,
        message=message,
    )


# ============================================================================
# The Context-Preserving Assistant (Weather Chat Page & Endpoint)
# ============================================================================

@app.route("/chat", methods=["GET", "POST"])
async def chat():
    """
    Chat page and endpoint for The Context-Preserving Assistant.
    When the user asks about weather:
      1. Calls /api/settings using the user's Auth0 access token.
      2. Reads the user's home city and preferred units.
      3. Calls Open-Meteo Geocoding & Forecast APIs.
      4. Replies like: 'Your home city is X, it's 28°C there.'
    """
    user = await get_current_user()
    if not user:
        if request.method == "POST":
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        return redirect(url_for("login"))

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"reply": "Please enter a message."})

        # Check if the user is asking about weather
        weather_keywords = [
            "weather",
            "temperature",
            "forecast",
            "temp",
            "rain",
            "sunny",
            "climate",
            "degrees",
            "hot",
            "cold",
            "outside",
        ]
        is_weather_query = any(k in message.lower() for k in weather_keywords)

        if is_weather_query:
            # 1. Retrieve the user's Auth0 access token
            token = await get_user_access_token()
            if not token:
                return jsonify({
                    "reply": (
                        "Could not find an active Auth0 access token in your session. "
                        "Please log out and log back in to grant API access."
                    )
                })

            # 2. Call /api/settings with the user's access token
            try:
                settings_data = await fetch_user_settings_via_api(token)
            except Exception as e:
                app.logger.error("Error calling /api/settings: %s", e)
                return jsonify({
                    "reply": f"Unable to fetch your settings via /api/settings: {str(e)}"
                })

            city = settings_data.get("city", "").strip()
            units = settings_data.get("units", "celsius").strip().lower()

            if not city:
                return jsonify({
                    "reply": (
                        "You haven't configured a home city yet! "
                        "Please go to Settings to set your home city."
                    )
                })

            # 3. Call Open-Meteo Geocoding API to resolve coordinates
            try:
                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    geo_resp = await http_client.get(
                        "https://geocoding-api.open-meteo.com/v1/search",
                        params={
                            "name": city,
                            "count": 1,
                            "language": "en",
                            "format": "json",
                        },
                    )
                    geo_data = geo_resp.json()
                    results = geo_data.get("results")
                    if not results:
                        return jsonify({
                            "reply": f"Your home city is {city}, but I couldn't find its location on Open-Meteo. Please check the spelling in Settings."
                        })

                    location = results[0]
                    lat = location.get("latitude")
                    lon = location.get("longitude")
                    city_name = location.get("name", city)

                    # 4. Call Open-Meteo Forecast API
                    temp_unit_param = "fahrenheit" if units == "fahrenheit" else "celsius"
                    weather_resp = await http_client.get(
                        "https://api.open-meteo.com/v1/forecast",
                        params={
                            "latitude": lat,
                            "longitude": lon,
                            "current": "temperature_2m",
                            "temperature_unit": temp_unit_param,
                        },
                    )
                    weather_data = weather_resp.json()
                    current = weather_data.get("current", {})
                    current_units = weather_data.get("current_units", {})
                    temp = current.get("temperature_2m")
                    unit_symbol = current_units.get("temperature_2m", "°C" if units == "celsius" else "°F")

                    # Reply format: 'Your home city is X, it's 28°C there.'
                    reply = f"Your home city is {city_name}, it's {temp}{unit_symbol} there."
                    return jsonify({"reply": reply})

            except Exception as e:
                app.logger.error("Open-Meteo weather lookup error: %s", e)
                return jsonify({
                    "reply": f"Sorry, I couldn't retrieve the weather for {city} right now: {str(e)}"
                })

        else:
            # Helpful assistant reply for non-weather queries
            user_display = user.get("name") or user.get("nickname") or "friend"
            reply = (
                f"Hello {user_display}! I'm your Context-Preserving Assistant. "
                "Ask me about the weather, and I will securely retrieve your home city "
                "via your Auth0 access token and check live conditions!"
            )
            return jsonify({"reply": reply})

    return render_template("chat.html", user=user)


# ============================================================================
# The Privacy-Aware RAG Bot (Auth0 FGA Protected)
# ============================================================================

@app.route("/rag", methods=["GET", "POST"])
async def rag():
    """
    The Privacy-Aware RAG Bot:
    For a question, finds matching documents by keyword search.
    BEFORE returning any retrieved document, calls FGA Check
    (user:<email>, viewer, document:<id>) using openfga-sdk.
    Drops every document that is denied.
    """
    user = await get_current_user()
    if not user:
        if request.method == "POST":
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        return redirect(url_for("login"))

    user_email = (user.get("email") or "employee@test.com").strip().lower()

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        question = (data.get("question") or data.get("message") or "").strip()
        simulated_email = (data.get("email") or "").strip().lower()
        effective_email = simulated_email if simulated_email else user_email

        if not question:
            return jsonify({
                "reply": "Please ask a question about internal company documents.",
                "status": "empty",
                "inspections": [],
            })

        result = await query_rag_pipeline(effective_email, question)
        return jsonify(result)

    # GET request
    return render_template(
        "rag.html",
        user=user,
        user_email=user_email,
        documents=DOCUMENTS,
        fga_store_id=FGA_STORE_ID or "Configured",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

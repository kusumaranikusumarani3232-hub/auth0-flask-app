"""Flask application with Auth0 authentication."""

import os
import uuid
from flask import Flask, redirect, render_template, request, session, url_for
from auth import LogoutOptions, auth0

app = Flask(__name__)

# Secret key for Flask session cookie encryption
app.secret_key = os.getenv("AUTH0_SECRET") or os.urandom(32).hex()


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


@app.route("/")
async def home():
    """Home route: shows welcome message + links if authenticated, otherwise login button."""
    user = await get_current_user()
    return render_template("index.html", user=user)


@app.route("/login")
async def login():
    """Initiate Auth0 authentication flow."""
    store_opts = get_store_options()
    login_url = await auth0.start_interactive_login(store_options=store_opts)
    return redirect(login_url)


@app.route("/callback")
async def callback():
    """Handle Auth0 redirect callback after authentication."""
    store_opts = get_store_options()
    try:
        result = await auth0.complete_interactive_login(
            request.url, store_options=store_opts
        )
        user = await auth0.get_user(store_options=store_opts)
        if not user and isinstance(result, dict) and "state_data" in result:
            user = result["state_data"].get("user")
        if user:
            session["user"] = user
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


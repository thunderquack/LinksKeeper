from __future__ import annotations

import os
import secrets
from urllib.parse import urlparse

from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()
login_manager = LoginManager()
oauth = OAuth()
migrate = Migrate()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return bool(self.password_hash and check_password_hash(self.password_hash, password))


class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    url = db.Column(db.Text, nullable=False)
    private_slug = db.Column(db.String(64), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    user = db.relationship("User", backref=db.backref("links", lazy="dynamic"))

    @property
    def path_key(self) -> str:
        return self.private_slug or str(self.id)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


def create_app() -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="../static",
        template_folder="../templates",
    )
    app.config.from_mapping(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///linkskeeper.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        APP_BASE_URL=os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/"),
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    oauth.init_app(app)

    register_google(app)
    register_routes(app)

    return app


def register_google(app: Flask) -> None:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return

    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def register_routes(app: Flask) -> None:
    @app.get("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            email = normalize_email(request.form.get("email", ""))
            password = request.form.get("password", "")
            user = db.session.scalar(select(User).where(User.email == email))
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "error")

        return render_template("login.html", google_enabled="google" in oauth._clients)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            email = normalize_email(request.form.get("email", ""))
            password = request.form.get("password", "")
            if not email or len(password) < 8:
                flash("Use a valid email and a password with at least 8 characters.", "error")
                return render_template("register.html")
            if db.session.scalar(select(User).where(User.email == email)):
                flash("This email is already registered.", "error")
                return render_template("register.html")

            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("dashboard"))

        return render_template("register.html")

    @app.get("/auth/google")
    def google_login():
        if "google" not in oauth._clients:
            abort(404)
        redirect_uri = url_for("google_callback", _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

    @app.get("/auth/google/callback")
    def google_callback():
        if "google" not in oauth._clients:
            abort(404)
        token = oauth.google.authorize_access_token()
        profile = token.get("userinfo") or oauth.google.userinfo()
        email = normalize_email(profile.get("email", ""))
        google_id = profile.get("sub")
        if not email or not google_id:
            flash("Google did not return an email address.", "error")
            return redirect(url_for("login"))

        user = db.session.scalar(select(User).where(User.google_id == google_id))
        if not user:
            user = db.session.scalar(select(User).where(User.email == email))
            if user:
                user.google_id = google_id
            else:
                user = User(email=email, google_id=google_id)
                db.session.add(user)
            db.session.commit()

        login_user(user)
        return redirect(url_for("dashboard"))

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        links = db.session.scalars(
            select(Link).where(Link.user_id == current_user.id).order_by(Link.id.desc())
        ).all()
        return render_template(
            "dashboard.html",
            links=links,
            base_url=app.config["APP_BASE_URL"],
        )

    @app.post("/links")
    @login_required
    def create_link():
        raw_url = request.form.get("url", "").strip()
        if not is_allowed_url(raw_url):
            flash("Enter a valid http or https URL.", "error")
            return redirect(url_for("dashboard"))

        private_slug = generate_private_slug() if request.form.get("private") == "1" else None
        link = Link(user_id=current_user.id, url=raw_url, private_slug=private_slug)
        db.session.add(link)
        db.session.commit()
        flash(f"Created {app.config['APP_BASE_URL']}/{link.path_key}", "success")
        return redirect(url_for("dashboard"))

    @app.get("/<path_key>")
    def redirect_link(path_key: str):
        link = find_link_by_path_key(path_key)
        if not link:
            abort(404)
        return redirect(link.url, code=302)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def is_allowed_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def generate_private_slug() -> str:
    while True:
        slug = secrets.token_urlsafe(24)
        if not db.session.scalar(select(Link).where(Link.private_slug == slug)):
            return slug


def find_link_by_path_key(path_key: str) -> Link | None:
    if path_key.isdecimal():
        return db.session.get(Link, int(path_key))
    return db.session.scalar(select(Link).where(Link.private_slug == path_key))

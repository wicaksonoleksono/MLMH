# app/ext/cache_buster.py
import os, time, click
from flask import current_app, url_for

VERSION_FILE = ".asset_version"   # lives in your instance folder by default

def _version_file_path(app):
    # Put it in instance_path so it persists across reloads and isn't in git
    os.makedirs(app.instance_path, exist_ok=True)
    return os.path.join(app.instance_path, VERSION_FILE)

def _read_version(app):
    p = _version_file_path(app)
    if os.path.exists(p):
        with open(p, "r") as f:
            return f.read().strip()
    return None

def _write_version(app, value):
    p = _version_file_path(app)
    with open(p, "w") as f:
        f.write(str(value))

def static_url(filename: str) -> str:
    """Jinja global: like url_for('static', ...), but auto-appends ?v=ASSET_VERSION"""
    v = current_app.config.get("ASSET_VERSION") or _read_version(current_app) or str(int(time.time()))
    return url_for("static", filename=filename, v=v)

def init_cache_buster(app):
    # 1) make version available in config and Jinja
    app.config.setdefault("ASSET_VERSION", _read_version(app) or str(int(time.time())))
    app.jinja_env.globals["static_url"] = static_url
    @app.cli.command("bump-assets")
    @click.option("--value", default=None, help="Optional explicit version value")
    def bump_assets(value):
        """Update asset version used in ?v=... for cache busting."""
        new_v = value or str(int(time.time()))
        _write_version(app, new_v)
        app.config["ASSET_VERSION"] = new_v
        click.echo(f"[OLKORECT] Asset version updated to: {new_v}")

    # 3) CLI: show current version
    @app.cli.command("show-assets-version")
    def show_assets_version():
        v = _read_version(app) or app.config.get("ASSET_VERSION")
        click.echo(f"ASSET_VERSION = {v}")

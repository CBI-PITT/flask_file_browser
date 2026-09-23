"""Shared fixtures for the flask_file_browser picker/browser contract tests.

These tests are render/static based: they execute the Jinja templates with a
stub context and assert the HTML/JS contracts that keep the Browse -> modal ->
embed -> select flow working.
"""

import json
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[1]
BROWSER_PKG = REPO_ROOT / "flask_file_browser"
BROWSER_TPL = BROWSER_PKG / "templates"
HOST_TPL = REPO_ROOT.parent / "generate_peace_json_test" / "flask_app" / "templates"

MODALS = ["flask_file_browser/modals/multiscale.html"]
BUTTONS = ["flask_file_browser/triggers/multiscale_trigger.html"]

NOW = "2026-09-23 17:00"
BRAINPI = {"brainpi_enabled": True, "brainpi_base_url": "https://brain-api.cbi.pitt.edu"}
USER = {"is_authenticated": True, "id": "iana"}


class _User:
    is_authenticated = True
    id = "iana"

    def get_id(self):
        return "iana"


def _url_for(endpoint, **kw):
    return f"/URL/{endpoint}" + (f"/{kw['filename']}" if kw.get("filename") else "")


@pytest.fixture(scope="session")
def jinja_env():
    env = Environment(loader=FileSystemLoader([str(BROWSER_TPL), str(HOST_TPL)]))
    env.filters["tojson"] = lambda v: json.dumps(v)
    env.globals["url_for"] = _url_for
    env.globals["get_flashed_messages"] = lambda with_categories=False: []
    env.globals["current_user"] = _User()
    return env


def make_ctx(base="dir", root=False):
    """A stub context mimicking get_path_data output for the given route base."""
    prefix = f"/browser/{base}"
    if root:
        return {
            "title": "CBI Browser", "header": "CBI Browser",
            "footer": "File Browser for the Center for Biologic Imaging",
            "logo": "images/cbi_logo.png",
            "parent_is_root": True, "parent_path": prefix, "parent_folder_name": "root",
            "current_path": prefix, "current_path_name": "root", "current_path_modtime": NOW,
            "current_path_entries": [1, 0],
            "dirs": [f"{prefix}/world"], "dirs_name": ["world"], "dirs_modtime": [NOW],
            "dirs_entries": [[12, 20]],
            "files": [], "files_name": [], "files_modtime": [], "files_size": [], "files_dl": [],
            "files_json": {},
            "html_path_split": ("browser", base),
            "all_parents": [(base, "/browser/" + base)],
        }
    return {
        "title": "CBI Browser", "header": "CBI Browser",
        "footer": "File Browser for the Center for Biologic Imaging",
        "logo": "images/cbi_logo.png",
        "parent_is_root": False, "parent_path": f"{prefix}/world", "parent_folder_name": "world",
        "current_path": f"{prefix}/world/sub", "current_path_name": "sub",
        "current_path_modtime": NOW,
        "current_path_entries": [1, 2],
        "dirs": [f"{prefix}/world/sub/iana"], "dirs_name": ["iana"], "dirs_modtime": [NOW],
        "dirs_entries": [[0, 1]],
        "files": [f"{prefix}/world/sub/a.tif", f"{prefix}/world/sub/b.ims"],
        "files_name": ["a.tif", "b.ims"], "files_modtime": [NOW, NOW],
        "files_size": [(1.5, "GB", 1500000000), (2.0, "GB", 2000000000)],
        "files_dl": ["/browser/download/x", "/browser/download/y"],
        "files_json": {
            f"{prefix}/world/sub/{name}": {
                "files": f"{prefix}/world/sub/{name}", "files_name": name,
                "files_size": [1.5, "GB", 1500], "files_modtime": NOW,
                "files_dl": "/browser/download/x",
            }
            for name in ["a.tif", "b.ims"]
        },
        "html_path_split": ("browser", base, "world", "sub"),
        "all_parents": [
            ("sub", f"{prefix}/world/sub"),
            ("world", f"{prefix}/world"),
            (base, "/browser/" + base),
        ],
    }


def render_embed(env, ctx):
    return env.get_template("flask_file_browser/fl_browse_table_dir_embed.html").render(
        current_path=ctx, user=USER, gtag="", modals=MODALS, buttons=BUTTONS, **BRAINPI)


def render_full_page(env, ctx):
    return env.get_template("flask_file_browser/fl_browse_table_dir.html").render(
        current_path=ctx, user=USER, gtag="", modals=MODALS, buttons=BUTTONS, **BRAINPI)


def assets(html):
    """All stylesheet/script URLs referenced by the page."""
    return [m for m in __import__("re").findall(r'(?:href|src)="([^"]+)"', html)
            if m.endswith((".css", ".js"))]


def read_template(name):
    return (BROWSER_TPL / "flask_file_browser" / name).read_text()

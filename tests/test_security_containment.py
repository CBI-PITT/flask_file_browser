"""Regression guards for the path-containment and auth fixes (2026-09-23).

The 2026-09-23 audit found that URL-encoded traversal (%2e%2e) escaped the
browsable roots and that get_file_path/imaris_info/dir_json required no login.
These tests pin the fixes.
"""

import os

import pytest

from conftest import BROWSER_PKG, security_app, security_client, security_login  # noqa: F401


def test_from_html_to_path_rejects_dotdot(tmp_path):
    from flask_file_browser.utils import from_html_to_path
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(PermissionError):
        from_html_to_path("/dir/cbi/x/../../etc", {"cbi": str(root)})


def test_from_html_to_path_rejects_symlink_escape(tmp_path):
    from flask_file_browser.utils import from_html_to_path
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, root / "link")
    with pytest.raises(PermissionError):
        from_html_to_path("/dir/cbi/link/secret", {"cbi": str(root)})


def test_from_html_to_path_allows_inside_root(tmp_path):
    from flask_file_browser.utils import from_html_to_path
    root = tmp_path / "root"
    sub = root / "sub"
    sub.mkdir(parents=True)
    resolved = from_html_to_path("/dir/cbi/sub/file", {"cbi": str(root)})
    assert resolved == os.path.join(str(root), "sub", "file")


def test_get_file_path_requires_login(security_client):
    resp = security_client.get("/browser/get_file_path/cbi/Iana")
    assert resp.status_code == 302, "get_file_path must require login"


def test_dir_json_requires_login(security_client):
    resp = security_client.get("/browser/dir_json/cbi")
    assert resp.status_code == 302, "dir_json must require login"


def test_imaris_info_requires_login(security_client):
    resp = security_client.get("/browser/imaris_info/cbi/Iana")
    assert resp.status_code == 302, "imaris_info must require login"


def test_file_path_rejects_encoded_traversal(security_client, security_login):
    security_login("iana")
    resp = security_client.get("/browser/get_file_path/cbi/Iana/%2e%2e/%2e%2e/etc/hostname")
    assert resp.status_code == 403, "encoded traversal must be rejected, not resolved"


def test_file_path_inside_root_ok(security_client, security_login):
    security_login("iana")
    resp = security_client.get(
        "/browser/get_file_path/cbi/Iana/src/peace/flask_file_browser_test/flask_file_browser/settings.ini")
    assert resp.status_code == 200
    assert resp.get_json()["file_path"].endswith("settings.ini")


def test_dir_download_blocked_for_non_owner(security_client, security_login):
    """The username gate must keep other users out of /h20/CBI/<user> dirs."""
    security_login("other-user")
    resp = security_client.get(
        "/browser/dir/cbi/Iana/src/peace/flask_file_browser_test/flask_file_browser/settings.ini")
    assert resp.status_code == 302, "non-owners must be redirected away from other users' dirs"


def test_route_bases_unaffected():
    """The embed/full-page routes and picker contract stay in place."""
    fs_browse = (BROWSER_PKG / "fs_browse.py").read_text()
    assert "base_embed = '/dir_embed/'" in fs_browse
    assert "base = '/dir/'" in fs_browse

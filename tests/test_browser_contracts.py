"""Regression guards for the embedded browser page (the PEACE picker iframe)
and the full-page /browser/dir/ view.

These exist because three separate refactors broke the picker:
  1. a dropped </script> made the whole inline JS never execute,
  2. a dropped Bootstrap bundle made data-bs-toggle modal buttons inert,
  3. asset/version drift (double bundles, BS4 APIs).
Each test below pins one of those contracts.
"""

import json
import re

import pytest

from conftest import (
    BROWSER_PKG,
    assets,
    make_ctx,
    read_template,
    render_embed,
    render_full_page,
)

SCRIPT_TEMPLATES = [
    "fl_browse_table_scripts.html",
    "fl_browse_table_body.html",
    "fl_browse_table_dir_embed.html",
    "fl_browse_table_dir.html",
    "browser_base.html",
]

MODAL_IDS = [
    "brainModal", "brainModalLabel", "brainModalFileSize", "brainModalUpdated",
    "brainModalFileSlug", "brainModalSelectBtn", "closeFileModalBtn",
    "brainFolderModal", "brainFolderModalText", "brainFolderModalSelectBtn",
    "multiscale", "multiscaleTrigger",
]


def _assert_scripts_balanced(html, label):
    assert html.count("<script") == html.count("</script>"), (
        f"{label}: <script> tags unbalanced — unterminated scripts never execute "
        f"and silently kill the modal wiring"
    )


def _assert_asset_set(html, label):
    found = assets(html)
    bundles = [a for a in found if "bootstrap.bundle.min.js" in a]
    jquery = [a for a in found if a.startswith("https://code.jquery.com/jquery")]
    datatables_js = [a for a in found if "dataTables.bootstrap5.min.js" in a]
    datatables_css = [a for a in found if "dataTables.bootstrap5.min.css" in a]
    assert len(bundles) == 1, f"{label}: exactly one bootstrap bundle required (found {len(bundles)}) — missing means data-bs-toggle modal buttons are silently inert; duplicated means double data-API registration"
    assert len(jquery) == 1, f"{label}: exactly one jQuery required (found {len(jquery)})"
    assert len(datatables_js) == 1, f"{label}: DataTables JS missing"
    assert len(datatables_css) == 1, f"{label}: DataTables CSS missing"
    for legacy in ("bootstrap@4", "popper", "bootstrapv5.1.3"):
        assert not any(legacy.lower() in a.lower() for a in found), (
            f"{label}: legacy asset {legacy} must not be loaded"
        )


@pytest.mark.parametrize("root", [False, True], ids=["deep", "root"])
def test_embed_asset_set_modal_capable(jinja_env, root):
    """The embed page must ship its own Bootstrap bundle (it does not extend
    browser_base.html) or the file/folder modal triggers do nothing."""
    html = render_embed(jinja_env, make_ctx(root=root))
    _assert_scripts_balanced(html, "embed page")
    _assert_asset_set(html, "embed page")


@pytest.mark.parametrize("root", [False, True], ids=["deep", "root"])
def test_full_page_asset_set(jinja_env, root):
    html = render_full_page(jinja_env, make_ctx(root=root))
    _assert_scripts_balanced(html, "full page")
    _assert_asset_set(html, "full page")


def test_script_tags_balanced_in_raw_templates():
    for name in SCRIPT_TEMPLATES:
        raw = read_template(name)
        assert raw.count("<script") == raw.count("</script>"), (
            f"{name}: raw template has unbalanced <script> tags — the last known "
            f"failure mode was a dropped closing </script> that killed all inline JS"
        )


def test_modal_triggers_and_fdata(jinja_env):
    html = render_embed(jinja_env, make_ctx())
    buttons = re.findall(r'<button[^>]*data-bs-toggle="modal"[^>]*>', html)
    assert buttons, "embed page must contain modal trigger buttons"
    for tag in buttons:
        target = re.search(r'data-bs-target="([^"]+)"', tag)
        assert target, f"modal trigger without data-bs-target: {tag}"
        assert target.group(1) in ("#brainModal", "#brainFolderModal", "#multiscale"), (
            f"unexpected modal target {target.group(1)}"
        )
        fdata = re.search(r"data-fdata='([^']*)'", tag)
        if fdata:
            payload = fdata.group(1).replace("&#34;", '"').replace("&quot;", '"').replace("&#39;", "'")
            json.loads(payload), f"unparseable data-fdata JSON: {payload}"
    for element_id in MODAL_IDS:
        assert f'id="{element_id}"' in html, f"missing modal element id {element_id}"


def test_brainpi_anchors_render_when_enabled(jinja_env):
    html = render_embed(jinja_env, make_ctx())
    for element_id in ("brainModalBrainPi", "brainFolderModalBrainPi"):
        assert f'id="{element_id}"' in html, f"{element_id} missing while brainpi is enabled"


def test_embed_inline_js_contracts():
    js = read_template("fl_browse_table_scripts.html")
    for contract in (
        "show.bs.modal",                       # modal population handlers
        "get_file_path/",                      # dynamicLink construction
        "current_path['html_path_split'][0]",  # link base is route-parameterized
        "getFieldId",                          # iframe -> parent selection flow
        "window.frameElement",
        "postMessage",
        "selectedPath",
        "fileName",
        "nextBrowserPath",
        "bootstrap.Modal.getInstance",         # requires the bundle (asset test)
        "fdata.files_name",
        "fdata.files_size",
        "fdata.files_modtime",
        "event.target.dataset.dynamicLink",    # link stored on the modal element
        "if (selpath)",                        # Select button only exists in picker mode
        "if (folderselpath)",
    ):
        assert contract in js, f"fl_browse_table_scripts.html lost contract: {contract}"


def test_select_buttons_only_in_picker_mode(jinja_env):
    """Select File / Select Folder only make sense when the browser is used as
    an operation picker. The embed page renders them; the full-page Browse tab
    must not (they dead-end there with 'Missing file path or field ID')."""
    embed = render_embed(jinja_env, make_ctx(base="dir_embed"))
    full = render_full_page(jinja_env, make_ctx(base="dir"))
    for element_id in ("brainModalSelectBtn", "brainFolderModalSelectBtn"):
        assert f'id="{element_id}"' in embed, f"{element_id} missing in picker mode"
        assert f'id="{element_id}"' not in full, (
            f"{element_id} must not render on the full-page browser"
        )
    assert "Select File" in embed and "Select Folder" in embed
    assert "Select File" not in full and "Select Folder" not in full
    # the rest of the modal stays useful while browsing
    for element_id in ("brainModalFileSlug", "brainModalBrainPi", "multiscaleTrigger"):
        assert f'id="{element_id}"' in full, f"{element_id} should remain on the full page"


def test_multiscale_modal_reads_link_from_modal_element():
    """multiscale.html derives its imaris_info fetch URL from the element that
    stores the dynamicLink; the Select button is picker-mode only."""
    content = read_template("modals/multiscale.html")
    assert "querySelector('#brainModal')" in content
    assert "#brainModalSelectBtn" not in content


def test_embed_page_chromeless(jinja_env):
    html = render_embed(jinja_env, make_ctx())
    body = html.split("<body", 1)[1]
    assert "navbar" not in body, "embed page must stay chrome-less (it renders inside the picker modal)"


def test_route_base_consistency(jinja_env):
    fs_browse = (BROWSER_PKG / "fs_browse.py").read_text()
    assert "base_embed = '/dir_embed/'" in fs_browse, "embed route base renamed or removed"
    assert "base = '/dir/'" in fs_browse, "full-page route base renamed or removed"

    ctx = make_ctx(base="dir_embed")
    html = render_embed(jinja_env, ctx)
    assert "/browser/get_file_path/" in html, "dynamicLink base no longer built from html_path_split[0]"
    assert "dir_embed" in html, "embed links must stay under /dir_embed/ to remain chrome-less"


def test_navbar_full_width():
    """The navbar and footer must span the full viewport (like the file table)
    instead of sitting in a centered max-width container."""
    base_raw = (BROWSER_PKG / "templates" / "flask_file_browser" / "browser_base.html").read_text()
    assert "container-xxl" not in base_raw, "centered max-width container crept back in"
    assert base_raw.count("container-fluid ffb-container") == 2, (
        "navbar and footer must both use the full-width container"
    )
    css = (BROWSER_PKG / "static" / "flask_file_browser" / "styles" / "browser.css").read_text()
    assert "1.5rem 1rem 2.5rem" in css, (
        "content must share the navbar/footer horizontal gutter so all edges align"
    )


def test_breadcrumb_inline_in_navbar(jinja_env):
    """The breadcrumb lives in the main navbar row (left, next to the brand),
    not in a separate sub-bar strip below it."""
    html = render_full_page(jinja_env, make_ctx())
    assert "ffb-navbar-path" not in html, "the breadcrumb sub-bar strip must be gone"
    brand_at = html.find("navbar-brand")
    breadcrumb_at = html.find("ffb-breadcrumb-wrap")
    collapse_at = html.find('id="ffbNavbar"')
    assert breadcrumb_at != -1, "breadcrumb wrapper missing from the full page"
    assert brand_at < breadcrumb_at < collapse_at, (
        "breadcrumb must render inside the navbar row, after the brand and before the nav links"
    )
    assert "bi-house-door-fill" in html, "breadcrumb home crumb missing"

    root_html = render_full_page(jinja_env, make_ctx(root=True))
    assert root_html.count("breadcrumb-item") == 1, "root listing should render a single home crumb"

    # base template ships no strip at all, so login/home/profile stay clean
    base_raw = (BROWSER_PKG / "templates" / "flask_file_browser" / "browser_base.html").read_text()
    assert "ffb-navbar-path" not in base_raw


def test_file_modal_population_elements(jinja_env):
    html = render_embed(jinja_env, make_ctx())
    js = read_template("fl_browse_table_scripts.html")
    for element_id, js_ref in (
        ("brainModalLabel", "#brainModalLabel"),
        ("brainModalFileSize", "#brainModalFileSize"),
        ("brainModalUpdated", "#brainModalUpdated"),
    ):
        assert f'id="{element_id}"' in html, f"missing {element_id} in embed HTML"
        assert js_ref in js, f"modal JS no longer populates {js_ref}"

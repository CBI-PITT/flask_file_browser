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
    BUTTONS,
    BROWSER_PKG,
    MODALS,
    USER,
    assets,
    make_ctx,
    read_template,
    render_embed,
    render_embed_picker_hidden,
    render_embed_with_dash,
    render_full_page,
    render_full_page_with_dash,
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
    "brainFolderModalNeuroglancer",
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


def test_neuroglancer_anchor_in_folder_modal(jinja_env):
    """The Neuroglancer button lives in the folder modal footer (folder-row
    click), next to BrAinPI, only while brainpi is enabled."""
    raw = read_template("fl_browse_table_body.html")
    folder_at = raw.find('id="brainFolderModal"')
    brainpi_at = raw.find('id="brainFolderModalBrainPi"')
    ng_at = raw.find('id="brainFolderModalNeuroglancer"')
    assert folder_at != -1 and brainpi_at != -1 and ng_at != -1, (
        "Neuroglancer anchor missing from the folder modal"
    )
    assert folder_at < brainpi_at < ng_at < raw.find('id="brainFolderModalSelectBtn"'), (
        "Neuroglancer anchor must sit in the folder modal footer, after BrAinPI"
    )

    html = render_embed(jinja_env, make_ctx())
    assert 'id="brainFolderModalNeuroglancer"' in html
    assert 'Neuroglancer' in html

    full = render_full_page(jinja_env, make_ctx())
    assert 'id="brainFolderModalNeuroglancer"' in full

    # disabled: the anchor and its JS must both be gone
    disabled = jinja_env.get_template("flask_file_browser/fl_browse_table_dir_embed.html").render(
        current_path=make_ctx(), user=USER, gtag="", modals=MODALS, buttons=BUTTONS,
        brainpi_enabled=False, brainpi_base_url="", brainpi_neuroglancer_url="")
    assert 'id="brainFolderModalNeuroglancer"' not in disabled, (
        "Neuroglancer anchor leaked while brainpi is disabled"
    )
    assert "configureBrainregNgButton" not in disabled, (
        "Neuroglancer JS leaked while brainpi is disabled"
    )


def test_neuroglancer_js_contracts():
    """The brainreg Neuroglancer flow: 'brainreg' path gate, /dir_json/ check
    for the brainreg output contents, per-file precomputed lookup via BrAinPI,
    and a client-side #! state with boundaries at 50% opacity. The files are
    the BrAinPI-friendly _ng OME copies written by the brainreg operation
    (the plain originals fail BrAinPI's TCZYXS validation)."""
    js = read_template("fl_browse_table_scripts.html")
    for contract in (
        "configureBrainregNgButton",
        "neuroglancerBaseUrl",
        ".includes('brainreg')",
        "replace('get_file_path', 'dir_json')",
        "brainregNgRequiredFiles.every",
        "brainreg.json",
        "downsampled_ng.tif",
        "boundaries_ng.tif",
        "path_to_html_options",
        "'precomputed://'",
        "opacity = 0.5",
        "'/#!'",
        "encodeURIComponent(JSON.stringify(state))",
        "get_file_path/",                                  # real-path lookup reuse
        "layers.push",                                     # downsampled under boundaries
        "brainregNgSampleRange",                           # per-layer data sampling
        "brainregNgTypedArrays",                           # dtype -> TypedArray map
        "'/info'",                                         # precomputed info lookup
        "response.arrayBuffer()",                          # raw plane decode
        "0-${sizeX}_0-${sizeY}_${z}-${z + 1}",             # chunk route (exclusive stop)
        "normalized: { range: range }",                    # pre-set 5-95% contrast
        "'4panel-alt'",                                    # 3 orthogonal views + 3D
    ):
        assert contract in js, f"fl_browse_table_scripts.html lost Neuroglancer contract: {contract}"
    # the originals must no longer be requested (they fail BrAinPI)
    js_body = js.split("brainregNgRequiredFiles", 1)[1]
    assert "downsampled.tiff" not in js_body and "boundaries.tiff" not in js_body, (
        "Neuroglancer flow must request the _ng OME copies, not the plain originals"
    )
    assert "{ type: 'xy' }" not in js_body, (
        "the brainreg viewer must open in the 4panel-alt layout"
    )


def test_neuroglancer_url_glue():
    """fs_browse.py must read neuroglancer_url from settings.ini and pass it
    to both renders (full page + embed)."""
    fs_browse = (BROWSER_PKG / "fs_browse.py").read_text()
    assert "neuroglancer_url" in fs_browse, "neuroglancer_url no longer read from settings"
    assert fs_browse.count("brainpi_neuroglancer_url=brainpi_neuroglancer_url") == 2, (
        "brainpi_neuroglancer_url must be passed to both renders"
    )
    settings_raw = (BROWSER_PKG / "settings.ini").read_text()
    assert "neuroglancer_url" in settings_raw


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


def test_embed_breadcrumbs_render(jinja_env):
    """The chrome-less embed picker must render its own breadcrumb strip so
    users can reach ancestor directories (the full page keeps its navbar one)."""
    html = render_embed(jinja_env, make_ctx(base="dir_embed"))
    assert "ffb-breadcrumb-embed" in html, "embed breadcrumb strip missing"
    assert "bi-house-door-fill" in html, "home crumb missing in the embed strip"
    # ancestors are links under the embed route base; the current dir is active
    assert '<a href="/browser/dir_embed/world">' in html, "ancestor crumb not linked under /dir_embed/"
    assert 'aria-current="page"' in html, "current directory crumb not marked active"
    # the full page must not render the embed strip (its breadcrumb lives in the navbar)
    full = render_full_page(jinja_env, make_ctx(base="dir"))
    assert "ffb-breadcrumb-embed" not in full, "embed breadcrumb strip leaked onto the full page"

    root_html = render_embed(jinja_env, make_ctx(base="dir_embed", root=True))
    assert root_html.count("breadcrumb-item") == 1, "root listing should render a single home crumb"


def test_embed_up_one_level(jinja_env):
    """The embed picker gets an up-one-level link to the parent directory;
    it disappears at the root listing (parent_path is a self-link there)."""
    deep = render_embed(jinja_env, make_ctx(base="dir_embed"))
    up_at = deep.find("ffb-up-btn")
    assert up_at != -1, "up-one-level link missing in the embed picker"
    assert deep.find('href="/browser/dir_embed/world"', up_at) != -1, (
        "up link must point at the parent directory"
    )

    root_html = render_embed(jinja_env, make_ctx(base="dir_embed", root=True))
    assert "ffb-up-btn" not in root_html, "up link must not render at the root listing"


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


# --------------------------------------------------------------------------
# Data dashboard "Add to dashboard" button contracts
# --------------------------------------------------------------------------

def test_dashboard_button_renders_when_enabled(jinja_env):
    """The Add to dashboard button renders in the file modal for both browse
    contexts when the [dashboard] flag is on."""
    for html in (render_embed_with_dash(jinja_env, make_ctx()),
                 render_full_page_with_dash(jinja_env, make_ctx())):
        assert 'id="brainModalDashboard"' in html, "Add to dashboard button missing"
        assert "Add to dashboard" in html
        assert "bi-bar-chart-line" in html
        # hidden until the JS confirms the file is a .csv
        assert 'id="brainModalDashboard" class="btn btn-sm btn-outline-primary d-none"' in html


def test_dashboard_button_absent_when_flag_off(jinja_env):
    """Without the [dashboard] flag the button (and its JS) must not render;
    the brainpi buttons stay."""
    for html in (render_embed(jinja_env, make_ctx()),
                 render_full_page(jinja_env, make_ctx())):
        assert 'id="brainModalDashboard"' not in html
        assert "Add to dashboard" not in html
    assert 'id="brainModalBrainPi"' in render_full_page(jinja_env, make_ctx())


def test_dashboard_js_contracts():
    """The inline JS must gate the button on .csv files, resolve the real path
    via the existing get_file_path fetch, and POST it to the dashboard."""
    js = read_template("fl_browse_table_scripts.html")
    for contract in (
        "configureDashboardButton",          # extension gating helper
        "endsWith('.csv')",                  # CSV files only
        "const dashboardAddUrl",             # endpoint from settings.ini
        "{{ dashboard_add_url | tojson }}",  # jinja-injected, tojson-safe
        "dashboardAddBtn.dataset.pathLookupUrl",
        "JSON.stringify({ path: data.file_path })",  # POSTs the real path
        "Added",                             # in-modal success feedback
        "if (dashboardAddBtn)",              # button only exists when enabled
    ):
        assert contract in js, f"fl_browse_table_scripts.html lost dashboard contract: {contract}"
    # the show.bs.modal handler wires the button like the brainpi one
    assert "configureDashboardButton(\n      event.target.querySelector('#brainModalDashboard')" in js


def test_dashboard_vars_passed_by_routes():
    """fs_browse.py must read the [dashboard] section and pass the vars to
    both the full-page and embed renders."""
    fs_browse = (BROWSER_PKG / "fs_browse.py").read_text()
    assert "settings.getboolean('dashboard', 'enabled'" in fs_browse
    assert "settings.get('dashboard', 'add_url'" in fs_browse
    assert fs_browse.count("dashboard_enabled=dashboard_enabled") == 2, (
        "dashboard vars must be passed to both the full-page and embed renders")
    assert fs_browse.count("dashboard_add_url=dashboard_add_url") == 2
    settings_raw = (BROWSER_PKG / "settings.ini").read_text()
    assert "[dashboard]" in settings_raw
    assert "add_url = /dashboard/api/add_csv" in settings_raw


# --------------------------------------------------------------------------
# Dashboard picker mode (?picker=0) contracts
# --------------------------------------------------------------------------

def test_picker_hidden_embed_hides_select_buttons(jinja_env):
    """The ?picker=0 embed (dashboard picker) hides the dead-end Select
    File/Folder buttons but keeps the file-modal actions working."""
    html = render_embed_picker_hidden(jinja_env, make_ctx(base="dir_embed"))
    for element_id in ("brainModalSelectBtn", "brainFolderModalSelectBtn"):
        assert f'id="{element_id}"' not in html, f"{element_id} must not render in ?picker=0 mode"
    assert "Select File" not in html and "Select Folder" not in html
    # the rest of the modal stays useful without the picker host
    for element_id in ("brainModalFileSlug", "brainModalDashboard", "brainModalBrainPi"):
        assert f'id="{element_id}"' in html, f"{element_id} must survive ?picker=0 mode"


def test_picker_hidden_links_carry_flag(jinja_env):
    """In ?picker=0 mode the in-iframe navigation links (breadcrumbs, up link,
    folder names) must carry ?picker=0 so the flag survives navigation."""
    html = render_embed_picker_hidden(jinja_env, make_ctx(base="dir_embed"))
    assert 'href="/browser/dir_embed/world?picker=0"' in html, (
        "ancestor crumb must carry the picker flag"
    )
    up_at = html.find("ffb-up-btn")
    assert up_at != -1 and 'href="/browser/dir_embed/world?picker=0"' in html[up_at:], (
        "up link must carry the picker flag"
    )
    assert '<a class="ffb-name-link text-truncate" href="/browser/dir_embed/world/sub/iana?picker=0">' in html, (
        "folder name links must carry the picker flag"
    )


def test_default_embed_unchanged_by_picker_flag(jinja_env):
    """Without ?picker=0 (PEACE form picker, full page) nothing changes: the
    Select buttons stay and no picker flag may leak into links."""
    embed = render_embed(jinja_env, make_ctx(base="dir_embed"))
    for element_id in ("brainModalSelectBtn", "brainFolderModalSelectBtn"):
        assert f'id="{element_id}"' in embed, f"{element_id} missing in default picker mode"
    assert "?picker=0" not in embed, "picker flag must not leak into the default embed render"

    full = render_full_page(jinja_env, make_ctx(base="dir"))
    assert "?picker=0" not in full, "picker flag must not leak into the full-page render"
    assert 'id="brainModalSelectBtn"' not in full


def test_picker_hidden_js_free_of_select_handlers(jinja_env):
    """The scripts partial must attach no Select handlers when the buttons
    are absent (null guards), in both modes."""
    js = read_template("fl_browse_table_scripts.html")
    assert "if (selpath)" in js
    assert "if (folderselpath)" in js
    # the picker flag is route-driven, not JS-driven
    assert "picker_hidden" not in js


def test_picker_hidden_passed_by_route():
    """fs_browse.py must read ?picker=0 and pass picker_hidden to the embed
    render only (the full page has no picker concept)."""
    fs_browse = (BROWSER_PKG / "fs_browse.py").read_text()
    assert "request.args.get('picker', '') == '0'" in fs_browse, (
        "embed route must read the ?picker=0 flag"
    )
    assert fs_browse.count("picker_hidden=picker_hidden") == 1, (
        "picker_hidden must be passed to the embed render only"
    )
    # positional: the pass must sit inside the embed render call, after the
    # flag is read (a full-page call would NameError at request time)
    embed_tpl_at = fs_browse.find("'flask_file_browser/fl_browse_table_dir_embed.html'")
    read_at = fs_browse.find("request.args.get('picker', '') == '0'")
    pass_at = fs_browse.find("picker_hidden=picker_hidden")
    assert -1 not in (embed_tpl_at, read_at, pass_at)
    assert read_at < pass_at, "picker_hidden must be read before it is passed"
    assert embed_tpl_at < pass_at, "picker_hidden must be passed to the embed render"
    assert fs_browse.find("picker_hidden=picker_hidden", pass_at + 1) == -1, (
        "picker_hidden must not be passed to the full-page render"
    )
    embed_tpl = read_template("fl_browse_table_dir_embed.html")
    assert "picker_mode = not (picker_hidden | default(false))" in embed_tpl, (
        "embed template must derive picker_mode from picker_hidden"
    )
    body_tpl = read_template("fl_browse_table_body.html")
    assert "picker_qs | default('')" in body_tpl, (
        "folder links must keep the picker flag undefined-safe"
    )


def test_live_routes_render_with_picker_flag(security_client, security_login):
    """Live end-to-end: the full page and both embed variants render through
    the real blueprint, with the picker flag applied only to ?picker=0."""
    security_login()
    full = security_client.get("/browser/dir/")
    assert full.status_code == 200, "full-page browser render broke"
    assert 'id="brainModalSelectBtn"' not in full.get_data(as_text=True), (
        "full page must never render Select buttons"
    )
    assert "?picker=0" not in full.get_data(as_text=True), (
        "picker flag must not leak onto the full page"
    )

    embed_default = security_client.get("/browser/dir_embed/")
    assert embed_default.status_code == 200, "default embed render broke"
    assert 'id="brainModalSelectBtn"' in embed_default.get_data(as_text=True), (
        "default embed (PEACE picker) must keep the Select buttons"
    )
    assert "?picker=0" not in embed_default.get_data(as_text=True)

    embed_hidden = security_client.get("/browser/dir_embed/?picker=0")
    assert embed_hidden.status_code == 200, "?picker=0 embed render broke"
    html = embed_hidden.get_data(as_text=True)
    assert 'id="brainModalSelectBtn"' not in html, "Select buttons must hide with ?picker=0"
    assert "?picker=0" in html, "?picker=0 embed links must carry the flag"

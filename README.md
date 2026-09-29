# flask-file-browser

An installable Flask blueprint for browsing a server filesystem in a web UI.
Directory listings with breadcrumbs and file-type icons, file downloads, an
options modal per file, and integration hooks (Multiscale Info, BrAinPI 3D
viewer links, "Add to dashboard") — plus a chrome-less embed mode that other
pages use as a file/folder picker via `postMessage`.

The PEACE web app mounts this blueprint under `/browser`; the standalone dev
entry runs it on its own.

## The PEACE system

```
                       researcher (web browser)
                              │
                              ▼
              ┌───────────────────────────────┐
              │        Flask web app          │
              │  (generate_peace_json_test)   │
              └───────┬───────────────┬───────┘
              writes  │               │ mounts
                      ▼               ▼
         ┌──────────────────┐  ┌────────────────────────┐
         │ JSON task files  │  │     file browser       │
         │ (shared folder)  │  │ (flask_file_browser_   │
         └────────┬─────────┘  │ test) + Add-to-        │
                  │ polls      │ dashboard button       │
                  ▼            └───────────┬────────────┘
    ┌──────────────────────┐              │
    │  back-end daemon     │              ▼
    │  (peace_pipe_line_   │   ┌───────────────────────┐
    │  slurm_test)         │   │    data dashboard     │
    └──────────┬───────────┘   │    (data_dashboard)   │
               │ sbatch        └───────────▲───────────┘
               ▼                           │ results
    ┌──────────────────────┐               │
    │    SLURM cluster     │──── outputs ──┘
    │  (job arrays, GPUs)  │
    └──────────────────────┘
```

| Repository | Role |
|---|---|
| `../generate_peace_json_test/` | Flask web app that mounts this blueprint |
| `../peace_pipe_line_slurm_test/` | Back-end pipeline daemon |
| **`flask_file_browser_test` (this repo)** | File-browser blueprint (`flask_file_browser`) |
| `../data_dashboard/` | Dashboard blueprint receiving CSVs from this browser |

## Features

- **Full-page browser** (`/browser/dir/`) — DataTables listings with folder/file
  counts, breadcrumbs in the navbar row, up-one-level navigation, per-extension
  Bootstrap icons, sorting.
- **Embed picker mode** (`/browser/dir_embed/`) — a chrome-less page for
  embedding in an iframe. Selecting a file or folder posts a message to the
  parent page with the payload `{fieldId, selectedPath, fileName,
  nextBrowserPath}`; the host form fills its hidden input and can trigger
  output autofill. This is how the PEACE forms and workflow builder pick paths.
- **File modal** — Download (size-limited), Multiscale Info for `.ims` files,
  **BrAinPI** 3D-viewer link for `.tif/.tiff/.ims` and `.ome.zarr/.omehans`,
  **Add to dashboard** button for `.csv` files.
- **Folder modal** — BrAinPI link for OME-Zarr/OMEhans volumes.
- **Authentication** — login page backed by LDAP/NTLM; anonymous read-only
  roots and authenticated roots are configured separately.

## Install and mount

```bash
# install the blueprint (from this repo)
python3 -m pip install ./flask_file_browser_test

# in your Flask app
from flask_file_browser import routes
routes.init_blueprint(app, prefix="/browser")
```

Standalone development server:

```bash
cd flask_file_browser
python3 flask_main_entry.py
# → http://localhost:5001
```

The blueprint ships all of its own templates and static files — no
host-provided `base.html` is needed. (An older version inherited a host
template with `styles`/`content` blocks; the browser UI now extends its own
`browser_base.html`.)

## Configuration (`flask_file_browser/settings.ini`)

Copy `template_settings.ini` to `settings.ini` and edit. Key sections:

| Section / key | Meaning |
|---|---|
| `[app] name, logo` | branding shown on browser pages |
| `[browser] browser_active` | enable/disable browser routes |
| `[browser] max_dl_file_size_GB` | download size limit |
| `[dir_anon]` | read-only roots for anonymous users (`<name> = /path`) |
| `[dir_auth]` | roots for authenticated users (`<name> = /path`) |
| `[file_types]` | file extensions visible when type filtering is on |
| `[auth] bypass_auth` | **testing only** — logs in any user without checking credentials |
| `[auth] restrict_paths_to_matched_username` | users may only browse inside roots/subfolders matching their account |
| `[auth] restrict_files_to_listed_file_types` | apply the `[file_types]` filter |
| `[auth] secret_key` | Flask secret key — always change it |
| `[auth] login_limit` | rate limit, e.g. `100/day;60/hour;10/minute` |
| `[auth] domain_server, domain_port, domain_name` | LDAP/NTLM domain login |
| `[brainpi] enabled, base_url` | BrAinPI 3D-viewer buttons (appends `/path_to_html_options/?path=...`) |
| `[dashboard] enabled, add_url` | "Add to dashboard" button for `.csv` files (must match the dashboard blueprint's prefix, e.g. `/dashboard/api/add_csv`) |
| `[GA4] gtag` | optional Google Analytics 4 tag |

## Security model

- Path endpoints require login (unless a root is configured as anonymous).
- All requested paths are resolved against the configured browsable roots with
  real-path containment; `..` traversal and symlink escapes are rejected.
- When `restrict_paths_to_matched_username` is on, authenticated users can
  browse only their own subfolder under the configured roots.
- Login is rate-limited per the `[auth] login_limit` setting.
- Set a strong random `secret_key` and keep `bypass_auth = False` outside
  testing.

## Embed picker contract

Host pages open `/browser/dir_embed/?path=<start>` in a modal iframe and
receive the selection via `postMessage`:

```js
window.addEventListener('message', (event) => {
    // event.data = {fieldId, selectedPath, fileName, nextBrowserPath}
});
```

Select buttons appear only in picker mode; the full-page browser shows
Download/BrAinPI/Multiscale actions instead.

## Tests

```bash
python3 -m pytest
```

Three test modules (~30 tests) are render/static contracts: balanced script
tags, exactly one Bootstrap bundle/jQuery/DataTables per page, modal triggers
with valid `data-fdata` JSON, inline JS contracts (modal handlers, `postMessage`
payload, picker glue), chrome-less embed, breadcrumb layout, path-containment
and auth security checks. The suite executes Jinja templates with stub
contexts — no browser or filesystem fixtures needed.

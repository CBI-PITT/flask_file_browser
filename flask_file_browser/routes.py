from flask import render_template
from flask import Blueprint
from flask import (
    request,
    flash,
    url_for,
    redirect,
    send_file,
    jsonify
    )

from .utils import get_path_data

extended_app = Blueprint(
    'flask_file_browser', __name__,
    template_folder='templates',
    static_folder='static'
)


@extended_app.route('/')
def extended_home():
    return render_template('extended_home.html')


# base entrypoint must always begin and end with '/' --> /my_entry/
base = '/browser/'


@extended_app.route(base + '<path:req_path>')
@extended_app.route(base, defaults={'req_path': ''})
def browse_fs(req_path):

    print(request.path)
    # print(request.remote_addr)
    # print(request.environ.get('HTTP_X_REAL_IP', request.remote_addr))
    # print(request.environ['REMOTE_ADDR'])
    # import pprint
    # pprint.pprint(request.environ)
    # print(request.access_route[-1])

    out = get_path_data(base, request)

    if isinstance(out, tuple) and out[0] == 'render_template':
        page_description, current_path = out[1:]
        return render_template(
            'fl_browse_table_dir.html',
            current_path={**page_description, **current_path},
            user=auth.user_info(),
            gtag=config.settings.get('GA4', 'gtag')
        )
    else:
        return out

# base entrypoint must always begin and end with '/' --> /my_entry/
base_json = '/browser_json/'

@extended_app.route(base_json + '<path:req_path>')
@extended_app.route(base_json, defaults={'req_path': ''})
def browse_fs_json(req_path):

    print(request.path)

    out = get_path_data(base, request)

    if isinstance(out, tuple) and out[0] == 'render_template':
        page_description, current_path = out[1:]
        return jsonify({**page_description, **current_path})
    else:
        return 'This did not return a JSON, maybe you have the wrong path'

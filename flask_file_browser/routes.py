# from flask import render_template
# from flask import Blueprint
# from flask import (
#     request,
#     flash,
#     url_for,
#     redirect,
#     send_file,
#     jsonify,
#     Flask
#     )

# from utils import get_path_data, get_config
# import os
# import auth

# extended_app = Blueprint(
#     'flask_file_browser', __name__,
#     template_folder='templates',
#     static_folder='static'
# )
# # Create the Flask application
# app = Flask(__name__)
# ## Grab settings information from config.ini file

# settings = get_config('settings.ini')


# # TEMPLATE_DIR = os.path.abspath(settings.get('app','templates_location'))
# # STATIC_DIR = os.path.abspath(settings.get('app','static_location'))
# LOGO = settings.get('app','logo') #Relative to STATIC_DIR
# # APP_NAME = settings.get('app','name')
# browser_active = settings.getboolean('browser','browser_active')
# if browser_active:
#     print('Initiating auth functionality')
#     from auth import setup_auth
#     app,login_manager = setup_auth(app,settings)
# else:
#     from auth import setup_NO_auth
#     app, login_manager = setup_NO_auth(app)
# @extended_app.route('/')
# def home():
#     """
#     Landing zone for BrainPi
#     """
#     return render_template('home.html',
#                            browser_active=browser_active,
#                         #    user=auth.user_info(),
#                            app_name=settings.get('app','name'),
#                            app_description=settings.get('app','description'),
#                            app_motto=settings.get('app','motto'),
#                            app_logo=LOGO,
#                            page_name='Home',
#                            gtag=settings.get('GA4','gtag'))


# # base entrypoint must always begin and end with '/' --> /my_entry/
# base = '/browser/'


# @extended_app.route(base + '<path:req_path>')
# @extended_app.route(base, defaults={'req_path': ''})
# def browse_fs(req_path):

#     print(request.path)
#     # print(request.remote_addr)
#     # print(request.environ.get('HTTP_X_REAL_IP', request.remote_addr))
#     # print(request.environ['REMOTE_ADDR'])
#     # import pprint
#     # pprint.pprint(request.environ)
#     # print(request.access_route[-1])

#     out = get_path_data(base, request)

#     if isinstance(out, tuple) and out[0] == 'render_template':
#         page_description, current_path = out[1:]
#         return render_template(
#             'fl_browse_table_dir.html',
#             current_path={**page_description, **current_path},
#             user=auth.user_info(),
#             gtag=config.settings.get('GA4', 'gtag')
#         )
#     else:
#         return out

# # base entrypoint must always begin and end with '/' --> /my_entry/
# base_json = '/browser_json/'

# @extended_app.route(base_json + '<path:req_path>')
# @extended_app.route(base_json, defaults={'req_path': ''})
# def browse_fs_json(req_path):

#     print(request.path)

#     out = get_path_data(base, request)

#     if isinstance(out, tuple) and out[0] == 'render_template':
#         page_description, current_path = out[1:]
#         return jsonify({**page_description, **current_path})
#     else:
#         return 'This did not return a JSON, maybe you have the wrong path'


# # Register the blueprint
# app.register_blueprint(extended_app)

# if __name__ == '__main__':
#     # Run the app on port 5001
#     app.run(host='0.0.0.0', port=5001, debug=True)

import os
import flask
from flask import request, render_template, Blueprint, jsonify
from .utils import get_config,get_html_split_and_associated_file_path,split_html
from flask_file_browser import auth

import importlib.resources as pkg_resources

routes_script_folder = os.path.dirname(__file__)
settings = get_config(os.path.join(routes_script_folder, 'settings.ini'))

# extended_app.config["DEBUG"] = settings.getboolean('app','debug')
def init_blueprint(app, settings=settings,prefix='/browser'):
    # TEMPLATE_DIR = os.path.abspath(settings.get('app','templates_location'))
    # TEMPLATE_DIR = os.path.join(routes_script_folder, settings.get('app','templates_location'))
    TEMPLATE_DIR = str(pkg_resources.files(__package__) / 'templates')
    # STATIC_DIR = os.path.abspath(settings.get('app','static_location'))
    # STATIC_DIR = os.path.join(routes_script_folder, settings.get('app','static_location'))
    STATIC_DIR = str(pkg_resources.files(__package__) / 'static')
    LOGO = settings.get('app','logo') #Relative to STATIC_DIR
    APP_NAME = settings.get('app','name')


    # Establish FLASK app
    # extended_app = flask.Flask(__name__,template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
    extended_app = Blueprint(
        'flask_file_browser', __name__,
        template_folder=TEMPLATE_DIR,
        static_folder=STATIC_DIR
    )
    browser_active = settings.getboolean('browser','browser_active')

    # Must init auth first to get login_manager
    if browser_active:
        print('Initiating auth functionality')
        from .auth import setup_auth
        extended_app,login_manager = setup_auth(app, extended_app)
    else:
        from .auth import setup_NO_auth
        extended_app, login_manager = setup_NO_auth(app, extended_app)

    if browser_active:
        print('Initiating browser functionality')
        from .fs_browse import initiate_browseable
        extended_app = initiate_browseable(extended_app,settings)
    else:
        from .fs_browse import initiate_NOT_browseable
        extended_app = initiate_NOT_browseable(extended_app, settings)


    print('Initiating Landing Zone')
    @extended_app.route('/', methods=['GET'])
    def extended_home():
        """
        Landing zone for BrainPi
        """
        return render_template(
            'flask_file_browser/extended_home.html',
            browser_active=browser_active,
            user=auth.user_info(),
            app_name=settings.get('app','name'),
            app_description=settings.get('app','description'),
            app_motto=settings.get('app','motto'),
            app_logo=LOGO,
            page_name='Home',
            gtag=settings.get('GA4','gtag')
        )

    @extended_app.route('/get_file_path/<path:html_path>', methods=['GET'])
    def file_path(html_path):
        url_tuple = split_html(request.path)
        bp_tuple = url_tuple[0]
        bp_prefix = '/' + url_tuple[0]
        request.path ='/' + '/'.join(url_tuple[1:])
        # (f"Full path: {request.path}")  # The full path requested
        # print(f"html_path: {html_path}") # The dynamic subpath
        file_path = get_html_split_and_associated_file_path(settings,request)
        return {"file_path": f"{file_path[1]}"}

    @extended_app.route('/imaris_info/<path:html_path>', methods=['GET'])
    def imaris_info(html_path):
        from imaris_ims_file_reader import ims
        url_tuple = split_html(request.path)
        request.path ='/' + '/'.join(url_tuple[1:])
        file_path = get_html_split_and_associated_file_path(settings,request)
        f = ims(file_path[1])
        table = '''
<table class="table table-striped table-bordered">
<thead>
<tr>
<th>Level</th>
<th>Resolution</th>
<th>Shape</th>
</tr>
</thead>
<tbody>
'''
        for rl in range(f.ResolutionLevels):
            table = table + "<tr>"
            table = table + "<td>" + str(rl) +"</td>"
            table = table + "<td>" + str(f.metaData[(rl, 0, 0, 'resolution')]) + "</td>"
            table = table + "<td>" + str(f.metaData[(rl, 0, 0, 'shape')][-3:]) + "</td>"
            table = table + "</tr>"
        table += "</tbody></table>"
        return jsonify({"imaris_info": table})

    app.register_blueprint(extended_app, url_prefix=prefix)
    return app



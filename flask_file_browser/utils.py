from flask import (
    render_template,
    request,
    flash,
    url_for,
    redirect,
    send_file,
    jsonify
    )

import glob, os
import sys
from natsort import natsorted
import datetime


def split_html(req_path):
    html_path = req_path.split('/')
    return tuple((x for x in html_path if x != '' ))


def get_config(file='settings.ini',allow_no_value=True):
    import configparser
    # file = os.path.join(os.path.split(os.path.abspath(__file__))[0],file)
    file = os.path.join(sys.path[0], file)
    config = configparser.ConfigParser(allow_no_value=allow_no_value)
    config.read(file)
    return config


def num_dirs_files(path):
    for _, dirs, files in os.walk(path):
        return len(dirs), len(files)


def get_path_map(settings_config_parser_object, user_authenticated=False):
    '''
    Returns a dict where key=path_common_name and value=actual_file_system_path
    '''
    path_map = {}
    ## Collect anon paths
    for ii in settings_config_parser_object['dir_anon']:
        path_map[ii] = settings_config_parser_object['dir_anon'][ii]

    if not user_authenticated:
        return path_map

    for ii in settings_config_parser_object['dir_auth']:
        path_map[ii] = settings_config_parser_object['dir_auth'][ii]
    return path_map


def from_html_to_path(req_path, path_map):
    # print('UTIL line 101: {}'.format(req_path))
    html_path = split_html(req_path)
    # print('UTIL line 103: {}'.format(html_path))
    return os.path.join(
        path_map[html_path[1]], # returns the true FS path
        *html_path[2:]) # returns a unpacked list of all subpaths from html_path[1]


def from_path_to_html(path, path_map, req_path, entry_point):
    html_path = split_html(req_path)
    if len(html_path) == 1:
        return path.replace(path_map[html_path[0]],entry_point)
    else:
        return path.replace(path_map[html_path[1]],entry_point + html_path[1])


def is_file_type(file_type, path):
    '''
    file_type is file extension starting with '.'
    Examples: '.ims', '.tiff', '.nd2'

    if file_type is a list of types return True if even 1 match ['.ims','.tif','.nd2']

    return bool
    '''

    # orig_path = path
    if isinstance(file_type, str):
        file_type = [file_type]
    if path[-1] == '/':
        path = path[:-1]
    terminal_path_ext = os.path.splitext('a' + path)[-1]

    return any([x.lower() == terminal_path_ext.lower() for x in file_type])  # + \
    # [os.path.exists(os.path.join(orig_path,x)) for x in file_type] )
    # return file_type.lower() == os.path.splitext('a'+ path)[-1].lower()


def get_file_size(in_bytes):
    '''
    returns a tuple (number, suffix, sortindex) eg (900,GB,2)
    the table hack will sort by the sort index then the number otherwise
    3 GB will be 'smaller' than 5 kB
    '''
    suffixes = ('B','KB','MB','GB','TB','PB')
    a = 0
    while in_bytes > 1024:
        a += 1 #This will go up the suffixes tuple with each division
        in_bytes = in_bytes / 1024
    return round(in_bytes,2), suffixes[a], a


def get_path_data(base, request):
    # Split the requested path to a tuple that can be reused below
    html_path_split = split_html(request.path)
    print(html_path_split)

    # Extract settings information that can be reused
    # Doing this here allows changes to paths to be dynamic (ie changes can be made while server is live)
    # May want to change this so that each browser access does not require access to settings file on disk.
    ## DEFAULT ##  get_config(file='settings.ini',allow_no_value=True)
    settings = get_config(file='/h20/home/iana/bio/flask_file_browser/flask_file_browser/settings.ini')

    print("=================================\n", dict(settings), "\n===============================")

    page_description = {}
    page_description['title'] = settings['browser']['title']
    page_description['header'] = settings['browser']['header']
    page_description['footer'] = settings['browser']['footer']
    page_description['logo'] = settings['app']['logo']
    # print(page_description)

    # Determine what directories that users are allowed to browse
    # based on authentication status and boot them if the path is not valid
    path_map =  get_path_map(settings, current_user.is_authenticated)

    # user={'is_authenticated':current_user.is_authenticated, 'id':current_user.id if current_user.is_authenticated else None}

    if current_user.is_authenticated:

        # Read in group information
        groups =  get_config('groups.ini', allow_no_value=True)

        # Build a list of allowed folders
        allowed_list = [current_user.id.lower()]
        for ii in groups:  # Group names
            if ii.lower() == 'all':
                continue
            for oo in groups[ii]:  # Users in each group
                if current_user.id.lower() == oo.lower():  # Current user matches the user in the group
                    # print('Line 168')
                    allowed_list.append(ii.lower())
        print(allowed_list)

    # If browsing the root gather current_path info in a special way
    if len(html_path_split) == 1:

        to_browse = [x for x in path_map]
        to_browse = natsorted(to_browse)
        # print(to_browse)

        # Limit the paths that are seen by an authenticated user based on the contents of the next directory
        # limit by username and groups
        limited_list = []
        if current_user.is_authenticated:
            real_paths = [path_map[x] for x in to_browse]  # converts to real path
            # print(real_paths)
            for browse, path in zip(to_browse, real_paths):
                # print(browse)
                # print(path)
                interior_listing = glob.glob(os.path.join(path, '*'))
                # print(interior_listing)
                interior_listing = [os.path.relpath(x, path).lower() for x in interior_listing]
                # print(interior_listing)
                if browse in settings['dir_anon']:
                    limited_list.append(browse)
                elif current_user.id.lower() in groups['all']:
                    limited_list.append(browse)
                elif settings.getboolean('auth',
                                         'restrict_paths_to_matched_username') and current_user.id.lower() in interior_listing:
                    limited_list.append(browse)
                elif not settings.getboolean('auth', 'restrict_paths_to_matched_username'):
                    limited_list.append(browse)
                elif any([x.lower() in interior_listing for x in allowed_list]):
                    limited_list.append(browse)

                # print(interior_listing)
                to_browse = limited_list

        current_path = {}
        # current_path['root'] = base[:-1]
        current_path['files'] = []
        current_path['html_path_split'] = html_path_split
        current_path['current_path'] = base[:-1]
        current_path['current_path_name'] = base[1:-1]
        current_path['current_path_modtime'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%I")
        current_path['current_path_entries'] = (len(to_browse), 0)

        current_path['parent_path'] = base[:-1]
        current_path['parent_is_root'] = True
        current_path['parent_folder_name'] = base[1:-1]

        current_path['dirs'] = [path_map[x] for x in to_browse]  # converts to real path
        current_path['dirs_name'] = to_browse
        # print(current_path['dirs'])
        current_path['dirs_stat'] = [os.stat(x) for x in current_path['dirs']]
        # print(current_path['dirs_stat'])
        current_path['files_stat'] = []
        current_path['files_size'] = []
        current_path['files_name'] = []
        current_path['files_modtime'] = []

        current_path['dirs_entries'] = [ num_dirs_files(x) for x in current_path['dirs']]
        current_path['dirs_modtime'] = [time_format(x.st_mtime) for x in current_path['dirs_stat']]
        # print(current_path['dirs_entries'])

        ## Reconstruct html_paths
        current_path['dirs'] = to_browse
        current_path['files'] = []

        ## Tuples of each derivitive path
        current_path['all_parents'] = [
            (html_path_split[-(idx + 1)], '/' + os.path.join(*html_path_split[0:len(html_path_split) - idx])) for idx, _
            in enumerate(html_path_split)]

        ## Special case, some directories should be treated like files (ie. .zarr, .weave, .z_sharded)
        remove_dirs_idx = []
        for idx, _ in enumerate(current_path['dirs']):
            supported = fts.ng_links(current_path['dirs'][idx])
            if supported:
                remove_dirs_idx.append(idx)
                current_path['files'].append(supported)
                current_path['files_stat'].append(current_path['dirs_stat'][idx])
                current_path['files_size'].append((0, 'B', 0))
                current_path['files_modtime'].append(current_path['dirs_modtime'][idx])
                current_path['files_name'].append(current_path['dirs_name'][idx])

        # print(remove_dirs_idx)
        if remove_dirs_idx != []:
            current_path['dirs'] = [x for idx, x in enumerate(current_path['dirs']) if idx not in remove_dirs_idx]
            current_path['dirs_name'] = [x for idx, x in enumerate(current_path['dirs_name']) if
                                         idx not in remove_dirs_idx]
            current_path['dirs_stat'] = [x for idx, x in enumerate(current_path['dirs_stat']) if
                                         idx not in remove_dirs_idx]
            current_path['dirs_entries'] = [x for idx, x in enumerate(current_path['dirs_entries']) if
                                            idx not in remove_dirs_idx]
            current_path['dirs_modtime'] = [x for idx, x in enumerate(current_path['dirs_modtime']) if
                                            idx not in remove_dirs_idx]

        ## Determine what options each files has
        current_path['files_ng_slug'] = [fts.ng_links(x) for x in current_path['files']]
        current_path['files_ng_info'] = [os.path.join(x, 'info') if x is not None else None for x in
                                         current_path['files_ng_slug']]
        current_path['files_dl'] = [fts.downloadable(x, size=current_path['files_stat'][idx].st_size,
                                                     max_sizeGB=settings.getint('browser', 'max_dl_file_size_GB')) for
                                    idx, x in enumerate(current_path['files'])]

    else:

        try:
            print('Line 73')

            if html_path_split[1] not in path_map:
                flash('You are not authorized to browse to path {}'.format(request.path))
                return redirect(url_for('login'))

            ## Boot user if they are gaining access to an inappropriate folder
            ## Retain access to anon folders
            ##Retain access to everything if in 'all' group
            ## Determine if folders should be restricted to user-name-matched only
            ## Retain if folder name is in allowed_list of usernames / groups
            if len(html_path_split) >= 3 and \
                    not html_path_split[1].lower() in [x.lower() for x in settings['dir_anon']] and \
                    not current_user.id.lower() in [x.lower() for x in groups['all']] and \
                    settings.getboolean('auth', 'restrict_paths_to_matched_username') and \
                    not html_path_split[2].lower() in allowed_list:
                flash('You are not authorized to browse to path {}'.format(request.path))
                return redirect(url_for('login'))

            # Construct real paths from names in path_map dict
            to_browse =  from_html_to_path(request.path, path_map)
            print('Live 110')

            # Get current directory listing by Files, Directories and stats on each
            current_path = {}
            current_path['html_path_split'] = html_path_split
            current_path['current_path'] = request.path
            current_path['current_path_name'] = os.path.split(current_path['current_path'])[1]
            current_path['parent_path'] = '/' + os.path.join(*html_path_split[:-1]) if len(
                html_path_split) > 2 else base[:-1]
            current_path['current_path_entries'] =  num_dirs_files(to_browse)

            current_path['parent_is_root'] = False if len(html_path_split) > 2 else True
            current_path['parent_folder_name'] = html_path_split[-2]
            if os.path.isdir(to_browse):
                current_path['current_path_modtime'] = time_format(os.stat(to_browse).st_mtime)
            if os.path.isdir(to_browse):
                # current_path['isfile'] = False
                for root, dirs, files in os.walk(to_browse):
                    # current_path['root'] = root
                    current_path['dirs'] = dirs
                    current_path['files'] = files
                    break
                current_path['dirs'] = [os.path.join(root, x) for x in current_path['dirs']]
                current_path['files'] = [os.path.join(root, x) for x in current_path['files']]

                # keep only directories that have the correct user/group names
                if not html_path_split[1].lower() in [x.lower() for x in settings['dir_anon']] and \
                        current_user.is_authenticated and \
                        not current_user.id.lower() in [x.lower() for x in groups['all']]:

                    if settings.getboolean('auth', 'restrict_paths_to_matched_username'):
                        # For predictable filter ALWAYS filter on the html path and not the file system path
                        tmp_dirs = [x for x in current_path['dirs'] if
                                     from_path_to_html(x, path_map, request.path, base)[2].lower() in allowed_list]
                        tmp_dirs = [ from_path_to_html(x, path_map, request.path, base) for x in
                                    current_path['dirs']]
                        tmp_dirs = [ split_html(x) for x in tmp_dirs]
                        current_path['dirs'] = [x for x, y in zip(current_path['dirs'], tmp_dirs) if
                                                y[2].lower() in allowed_list]

                    if settings.getboolean('auth', 'restrict_files_to_listed_file_types'):
                        to_view = []
                        for ii in settings['file_types']:
                            # Further limit to the file type being filtered
                            current_files = [x for x in current_path['files'] if
                                              is_file_type(settings['file_types'][ii],  split_html(x)[
                                                 -1])]  # <-- add 'a' to make split consistent when files start with '.'
                            to_view = to_view + current_files
                        current_path['files'] = to_view

                current_path['dirs'] = natsorted(current_path['dirs'])
                current_path['files'] = natsorted(current_path['files'])

                current_path['dirs_name'] = [os.path.split(x)[-1] if x[-1] != '/' else os.path.split(x[:-1])[-1] for x
                                             in current_path['dirs']]
                current_path['dirs_stat'] = [os.stat(x) for x in current_path['dirs']]
                current_path['files_stat'] = [os.stat(x) for x in current_path['files']]
                current_path['files_size'] = [ get_file_size(x.st_size) for x in current_path['files_stat']]
                current_path['files_modtime'] = [time_format(x.st_mtime) for x in current_path['files_stat']]
                current_path['files_name'] = [os.path.split(x)[-1] if x[-1] != '/' else os.path.split(x[:-1])[-1] for x
                                              in current_path['files']]

                current_path['dirs_entries'] = [ num_dirs_files(x) for x in current_path['dirs']]
                current_path['dirs_modtime'] = [time_format(x.st_mtime) for x in current_path['dirs_stat']]

                ## Reconstruct html_paths
                current_path['dirs'] = [ from_path_to_html(x, path_map, request.path, base) for x in
                                        current_path['dirs']]
                current_path['files'] = [ from_path_to_html(x, path_map, request.path, base) for x in
                                         current_path['files']]

                ## Tuples of each derivitive path
                current_path['all_parents'] = [
                    (html_path_split[-(idx + 1)], '/' + os.path.join(*html_path_split[0:len(html_path_split) - idx]))
                    for idx, _ in enumerate(html_path_split)]

                ## Special case, some directories should be treated like files (ie. .zarr, .weave, .z_sharded)
                remove_dirs_idx = []
                for idx, _ in enumerate(current_path['dirs']):
                    supported = fts.ng_links(current_path['dirs'][idx])
                    if supported:
                        remove_dirs_idx.append(idx)
                        current_path['files'].append(supported)
                        current_path['files_stat'].append(current_path['dirs_stat'][idx])
                        current_path['files_size'].append((0, 'B', 0))
                        current_path['files_modtime'].append(current_path['dirs_modtime'][idx])
                        current_path['files_name'].append(current_path['dirs_name'][idx])

                # print(remove_dirs_idx)
                if remove_dirs_idx != []:
                    current_path['dirs'] = [x for idx, x in enumerate(current_path['dirs']) if
                                            idx not in remove_dirs_idx]
                    current_path['dirs_name'] = [x for idx, x in enumerate(current_path['dirs_name']) if
                                                 idx not in remove_dirs_idx]
                    current_path['dirs_stat'] = [x for idx, x in enumerate(current_path['dirs_stat']) if
                                                 idx not in remove_dirs_idx]
                    current_path['dirs_entries'] = [x for idx, x in enumerate(current_path['dirs_entries']) if
                                                    idx not in remove_dirs_idx]
                    current_path['dirs_modtime'] = [x for idx, x in enumerate(current_path['dirs_modtime']) if
                                                    idx not in remove_dirs_idx]

                ## Determine what options each files has
                current_path['files_ng_slug'] = [fts.ng_links(x) for x in current_path['files']]
                current_path['files_ng_info'] = [os.path.join(x, 'info') if x is not None else None for x in
                                                 current_path['files_ng_slug']]
                current_path['files_dl'] = [fts.downloadable(x, size=current_path['files_stat'][idx].st_size,
                                                             max_sizeGB=settings.getint('browser',
                                                                                        'max_dl_file_size_GB')) for
                                            idx, x in enumerate(current_path['files'])]

            elif os.path.isfile(to_browse):
                current_path['isFile'] = True
                # return jsonify(current_path)
                return send_file(to_browse, download_name=os.path.split(to_browse)[1], as_attachment=True)

            else:
                # If a non-file / dir is passed, move backward to the nearest file/dir
                return redirect(current_path['parent_path'])

        except Exception:
            flash('You must not be authorized to browse to path {}'.format(request.path))
            print(traceback.format_exc())
            return redirect(url_for('login'))

    '''
    Build a dict for each file with each available option
    This is used by javascript to build the modl
    '''
    files_json = {}
    for idx, file in enumerate(current_path['files']):
        files_json[file] = {}
        files_json[file]['files'] = file
        files_json[file]['files_name'] = current_path['files_name'][idx]
        files_json[file]['files_size'] = current_path['files_size'][idx]
        files_json[file]['files_modtime'] = current_path['files_modtime'][idx]
        files_json[file]['files_ng_slug'] = current_path['files_ng_slug'][
            idx]  # + '/?neuroglancer' if isinstance(current_path['files_ng_slug'][idx],str) else ''  #Assist with google analytics
        files_json[file]['files_ng_info'] = current_path['files_ng_info'][idx]
        files_json[file]['files_dl'] = current_path['files_dl'][idx]

    current_path['files_json'] = files_json
    # print(files_json)

    '''
    Everything above this builds 
    'page_description', 'current_path'
    This is the data passed to render template to build the browser
    Return renders the browser
    '''

    return 'render_template', page_description, current_path

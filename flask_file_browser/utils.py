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

def get_config(file='settings.ini',allow_no_value=True):
    """
    Load configuration settings from the created setting.ini file.

    This function reads configuration settings from a specified settings,ini file.
    It is primarily used for loading settings. It can be used for Sphinx 
    documentation generation if the file does not exist, it will fall back to a 
    template version of the file.

    Args:
        file (str, optional): The name of the INI file to load. Defaults to 'settings.ini'.
        allow_no_value (bool, optional): Whether to allow keys without values in the INI file. 
                                         Defaults to True.

    Returns:
        configparser.ConfigParser: A ConfigParser object containing the parsed configuration.
    """
    import configparser
    dir_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(dir_path, file)
    # This condition is used for documentation generation through sphinx and readTheDoc, plz always have settings.ini.
    if os.path.exists(file_path) is False:
        file_path = os.path.join(dir_path, 'template_' + file)
        print('sphinx generation',file_path)
    config = configparser.ConfigParser(allow_no_value=allow_no_value)
    config.read(file_path)
    return config

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


def get_file_size(path, parent=None):
    """
    Get the size of a file.

    Args:
        path (str): The file path.
        parent (str, optional): Parent directory (used for S3). Defaults to None.

    Returns:
        int: The size of the file in bytes.
    """
    if 's3://' in path:
        if s3_utils.s3_isfile(path):
            p, f = s3_utils.s3_path_split(path)
            parent, _, files, files_sizes, _ = s3_utils.s3_get_dir_contents(p)
            idx = files.index(f)
            return files_sizes[idx]
        else:
            return 0
    else:
        return os.stat(path).st_size

def get_mod_time(path):
    """
    Get the last modification time of a file or directory.

    Args:
        path (str): The path to the file or directory.

    Returns:
        datetime.datetime: The modification time.
    """
    if 's3://' in path:
        if s3_utils.s3_isfile(path):
            p, f = s3_utils.s3_path_split(path)
            parent, _, files, _, files_modified = s3_utils.s3_get_dir_contents(p)
            idx = files.index(f)
            return files_modified[idx]
        else:
            return datetime.datetime.now()
    else:
        return os.stat(path).st_mtime
    
def compress_flask_response(response, request, compression_level=6):
    """
    Compress a Flask response using gzip.

    Args:
        response (Flask.Response): The Flask response object.
        request (Flask.Request): The Flask request object.
        compression_level (int, optional): The gzip compression level. Defaults to 6.

    Returns:
        Flask.Response: The compressed response.
    """
    if response.direct_passthrough:
        return response

    request_headers = request.headers
    if 'Accept-Encoding' in request_headers and 'gzip' in request_headers['Accept-Encoding']:
        # Compress json
        out = gzip.compress(response.data, compression_level)
        response.data = out
        response.headers.add('Content-Encoding', 'gzip')
        # response.headers.add('Content-length', len(out))
    return response

def list_all_contents(path):
    """
    List all contents (files and directories) of a given path.

    Args:
        path (str): The directory path.

    Returns:
        list: A list of all files and directories in the path.
    """
    parent, dirs, files = get_dir_contents(path)
    dirs = [os.path.join(parent,x) for x in dirs]
    files = [os.path.join(parent, x) for x in files]
    return dirs + files
def get_dir_contents(path,skip_s3=False):
    """
    Get the contents of a directory, including subdirectories and files.

    Args:
        path (str): The directory path.
        skip_s3 (bool, optional): Whether to skip S3 directories. Defaults to False.

    Returns:
        tuple: A tuple containing the parent directory, subdirectories, and files.
    """
    if 's3://' in path:
        if skip_s3:
            return path, [], []
        parent, dirs, files, _, _ = s3_utils.s3_get_dir_contents(path)
        return f's3://{parent}', dirs, files
    else:
        for parent, dirs, files in os.walk(path):
            return parent, dirs, files
def isfile(path):
    """
    Check if a path is a file.

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path is a file, False otherwise.
    """
    if 's3://' in path:
        return s3_utils.s3_isfile(path)
    else:
        return os.path.isfile(path)
def isdir(path):
    """
    Check if a path is a directory.

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path is a directory, False otherwise.
    """
    # if 's3://' in path:
    #     return s3.isdir(path)
    if 's3://' in path:
        return s3_utils.s3_isdir(path)
    else:
        return os.path.isdir(path)
def format_file_size(in_bytes):
    '''
    returns a tuple (number, suffix, sortindex) eg (900,GB,2) 
    the table hack will sort by the sort index then the number otherwise
    3 GB will be 'smaller' than 5 kB

    Args:
        in_bytes (int): The file size in bytes.

    Returns:
        tuple: A tuple containing the formatted size, suffix, and sort index.
    '''
    suffixes = ('B','KB','MB','GB','TB','PB')
    a = 0
    while in_bytes > 1024:
        a += 1 #This will go up the suffixes tuple with each division
        in_bytes = in_bytes / 1024
    return round(in_bytes,2), suffixes[a], a
import flask
url_template = 'https://{}.s3.amazonaws.com/{}'
def send_file(path):
    """
    Send a file as a Flask response.

    Args:
        path (str): The file path.

    Returns:
        Flask response: A file response for downloading or redirecting.
    """
    if 's3://' in path:
        bucket, path_split = s3_utils.s3_get_bucket_and_path_parts(path)
        return redirect(
            url_template.format(bucket,'/'.join(path_split[1:]))
        )
    else:
        return flask.send_file(path, download_name=os.path.split(path)[1], as_attachment=True)

def get_html_split_and_associated_file_path(settings,request):
    """
    Get the split HTML path and the associated file system path.

    Args:
        config (object): Configuration settings.
        request (Flask.Request): The Flask request object.

    Returns:
        tuple: A tuple containing the split HTML path and the file system path.
    """
    # settings = config.settings
    path_map = get_path_map(settings,user_authenticated=True) #<-- Force user_auth=True to get all possible paths, in this way all ng links will be shareable to anyone
    datapath = from_html_to_path(request.path, path_map)
    
    path_split = split_html(request.path)
    return path_split, datapath
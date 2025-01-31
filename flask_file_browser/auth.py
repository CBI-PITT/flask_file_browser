# -*- coding: utf-8 -*-
"""
Created on Wed Mar 23 20:44:29 2022

@author: alpha
"""

'''
Windows domain auth:
    https://soshace.com/integrate-ldap-authentication-with-flask/
    https://ldap3.readthedocs.io/en/latest/connection.html

Flask login:
    https://www.digitalocean.com/community/tutorials/how-to-add-authentication-to-your-app-with-flask-login
    https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-v-user-logins

Flask limiter:
    https://flask-limiter.readthedocs.io/en/latest/
'''

from flask import (render_template, 
                   request, 
                   flash, 
                   redirect, 
                   url_for,
                   abort)

from flask_login import (LoginManager, 
                         login_user, 
                         UserMixin, 
                         current_user,
                         login_required,
                         logout_user)

def user_info():
    """
    Retrieve information about the currently logged-in user.

    Returns:
        dict: A dictionary containing the following keys:
              - 'is_authenticated': Whether the user is authenticated (bool).
              - 'id': The user's ID if authenticated, otherwise None.
    """
    return {'is_authenticated':current_user.is_authenticated, 'id':current_user.id if current_user.is_authenticated else None}

class User(UserMixin):
    def __init__(self,username):
        self.id = username

def setup_auth(app,extended_app):
    """
    Set up user authentication and session management for the Flask application.

    Configures:
    - Secure session cookies.
    - Login manager for managing user sessions.
    - Rate limiter to prevent brute force login attempts.
    - Routes for login, logout, and profile pages.

    Args:
        app (Flask): The Flask application instance.

    Returns:
        tuple: A tuple containing the modified Flask app and the LoginManager instance.
    """
    ## This import must remain here else circular import error
    from routes import settings
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    
    app.config['SESSION_COOKIE_SECURE'] = True
    
    ## KEY FOR TESTING ONLY ##
    app.secret_key = settings.get('auth','secret_key')
    
    ############################################################
    # Configure login manager
    ############################################################
    login_manager = LoginManager(app)
    login_manager.login_view = 'login'
    # login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User(user_id)
    
    
    ##########################################################
    # Configure login rate limiter
    ##########################################################
    
    # limiter = Limiter(app, key_func=get_remote_address)
    ##TODO Rate limiter needs to be in place where all workers can access
    #https://flask-limiter.readthedocs.io/en/stable/configuration.html#RATELIMIT_STORAGE_URI
    limiter = Limiter(get_remote_address,app=app,storage_uri="memory://")
    
    @extended_app.errorhandler(429)
    def ratelimit_handler(e):
        flash("Login ratelimit exceeded %s" % e.description)
        return redirect(url_for('flask_file_browser.flask_file_browser.login'))
    
    
    ##########################################################
    # Configure login routes
    ##########################################################


    @extended_app.route('/login')
    def login():
        if current_user.is_authenticated:
            flash('''
                  You are already signed in as user {}.
                  If this is not you, please logout
                  '''.format(current_user.id))
            return redirect(url_for('flask_file_browser.profile'))
        return render_template('login.html',
                               user=user_info(),
                               app_name=settings.get('app','name'),
                               page_name='Login',
                               gtag=settings.get('GA4','gtag'))
    
    

    @extended_app.route('/login', methods=['POST'])
    @limiter.limit(settings.get('auth','login_limit'))
    def login_post():
        
        remote_ip = request.remote_addr #<--Potential to log attempts and restrict number of tries
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        ## Check user against domain server
        user = False # Default to False for security
        if 'auth' in settings and not settings.getboolean('auth','bypass_auth'):
            user = domain_auth(username,
                               password,
                               domain_server=r"ldap://{}:{}".format(
                                   settings.get('auth','domain_server'),
                                   settings.get('auth','domain_port')
                                   ),
                               domain=settings.get('auth','domain_name')
                               ) # Return bool True/False if auth succeeds/fails and None if error
            
            if user == False:
                flash('''Your credentials are not valid''')
                return redirect(url_for('flask_file_browser.login'))
            if user is None:
                flash('''An error occured during login: please try again.
                      If the error persists, please report the problem''')
                return redirect(url_for('flask_file_browser.login'))
        else:
            user = True
    
        if user == False:
            flash('Please check your login details and try again.')
            return redirect(url_for('flask_file_browser.login')) # if the user doesn't exist or password is wrong, reload the page
    
        # if the above check passes, then we know the user has the right credentials
        login_user(load_user(username), remember=remember)  
        print('Got to here')
        return redirect(url_for('flask_file_browser.browse_fs'))
    
    
    
    
    # @app.route('/signup')
    # def signup():
    #     return render_template('signup.html')
    
    
    
    @extended_app.route('/profile')
    @login_required
    def profile():
        return render_template('profile.html',
                               user=user_info(),
                               app_name=settings.get('app','name'),
                               page_name='Profile',
                               gtag=settings.get('GA4','gtag'))
    
    
    
    @extended_app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('flask_file_browser.extended_home'))
    
    return extended_app,login_manager


def setup_NO_auth(app,extended_app):
    """
    Set up a Flask application with disabled authentication.

    This function disables all login routes and returns 404 errors for any login-related requests.

    Args:
        app (Flask): The Flask application instance.

    Returns:
        tuple: A tuple containing the modified Flask app and the LoginManager instance.
    """
    ## This import must remain here else circular import error
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    app.config['SESSION_COOKIE_SECURE'] = True

    ############################################################
    # Configure login manager
    ############################################################
    login_manager = LoginManager(app)
    login_manager.login_view = 'login'

    # login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        abort(404)

    ##########################################################
    # Configure login rate limiter
    ##########################################################

    # limiter = Limiter(app, key_func=get_remote_address)
    ##TODO Rate limiter needs to be in place where all workers can access
    # https://flask-limiter.readthedocs.io/en/stable/configuration.html#RATELIMIT_STORAGE_URI
    limiter = Limiter(get_remote_address, app=app, storage_uri="memory://")

    @extended_app.errorhandler(429)
    def ratelimit_handler(e):
        flash("Login ratelimit exceeded %s" % e.description)
        return abort(404)

    ##########################################################
    # Abort all login routes
    ##########################################################


    @extended_app.route('/login')
    def login():
        abort(404)

    @extended_app.route('/login', methods=['POST'])
    # @limiter.limit(settings.get('auth', 'login_limit'))
    def login_post():
        abort(404)

    @extended_app.route('/profile')
    # @login_required
    def profile():
        abort(404)

    @extended_app.route('/logout')
    def logout():
        return abort(404)

    return extended_app, login_manager


def domain_auth(user_name,password,domain_server=r"ldap://localhost:389",domain="mydomain"):
    """
    Attempts a simple verification of user account on windows domain server

    Args:
        user_name (str): The username to authenticate.
        password (str): The user's password.
        domain_server (str, optional): The domain server's address (LDAP URI). Defaults to 'ldap://localhost:389'.
        domain (str, optional): The domain name. Defaults to "mydomain".

    Returns:
        bool or None:
            - True if authentication succeeds.
            - False if authentication fails.
            - None if an error occurs during the connection.
    """
 
    from ldap3 import Server, Connection, ALL, NTLM
    
    
    user = domain + "\\" + user_name
    
    server = Server(domain_server, get_info=ALL)
     
    try:
        conn = Connection(server, user=user, password=password, authentication=NTLM)
        
        if conn.bind():
            print('Authentication successful as user: {}'.format(user_name))
            conn.unbind()
            # if conn.closed == True:
            #     return True
            return True
        else:
            print('Authentication Failed')
            return False
    except:
        print('An error occured while connecting to the domain server')
        return None
     

A Flask blueprint that enables browsing the file system.
It can be added to your main Flask app as follows:
```
$ pip install flask-file-browser
```
Then, in your project:
```
from flask_file_browser import routes
app = routes.init_blueprint(app, prefix="/browser")
```

where app is your main Flask app.

It will inherit the base.html template in your main app/templates.

The base.html template needs to define the following blocks:
- styles `{% block styles %}{% endblock %}`
- content `{% block content %}{% endblock %}`
  

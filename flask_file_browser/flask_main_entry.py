# This is the main file that will run the Flask app
from flask import Flask
from routes import init_blueprint  # Import the init function

app = Flask(__name__)
# Register the blueprint with settings
app = init_blueprint(app, prefix='/browser')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
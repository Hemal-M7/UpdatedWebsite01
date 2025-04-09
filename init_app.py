db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'mysecretkey'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
    db.init_app(app)  # Initialize here
    login_manager.init_app(app)  # Similarly for LoginManager
    bcrypt.init_app(app)  # Similarly for Bcrypt

    return app
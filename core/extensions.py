from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Instanciamos sem associar diretamente a uma "app" ainda (Application Factory)
db = SQLAlchemy()
login_manager = LoginManager()
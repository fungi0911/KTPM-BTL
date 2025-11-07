from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
jwt = JWTManager()
swagger = Swagger()

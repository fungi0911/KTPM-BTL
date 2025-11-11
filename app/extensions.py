from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger
from flask_jwt_extended import JWTManager
from pymongo import MongoClient

db = SQLAlchemy()
jwt = JWTManager()
swagger = Swagger()
mongo_client: MongoClient | None = None

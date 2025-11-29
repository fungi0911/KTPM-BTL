from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis
from pymongo import MongoClient
from redis import Redis

db = SQLAlchemy()
jwt = JWTManager()
swagger = Swagger()
mongo_client: MongoClient | None = None
redis_client: Redis | None = None

limiter = Limiter(key_func=get_remote_address)

redis_client = Redis(host="localhost", port=6379, decode_responses=True)

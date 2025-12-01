import os

class Config:
    
    #SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///D:s/KTPM-BTL/inventory.db")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "mysql+pymysql://root:123456@localhost:3306/ktpm")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key")
    JWT_ACCESS_TOKEN_EXPIRES = 7200  # 2h
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+2.5.9")
    MONGO_DB = os.getenv("MONGO_DB", "ktpm")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


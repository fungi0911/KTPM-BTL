import os

class Config:
    
    #SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:////Users/atula/Desktop/KTPM_BTL/inventory.db")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "mysql+pymysql://root:vttp1003@localhost:3306/ktpm")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret")
    JWT_ACCESS_TOKEN_EXPIRES = 7200  # 2h
    MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://ktpm:sonsoi@ktpm.d6lncqb.mongodb.net/?appName=KTPM")
    MONGO_DB = os.getenv("MONGO_DB", "ktpm")

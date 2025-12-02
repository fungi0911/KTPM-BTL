from ..extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default="staff")
    version = db.Column(db.Integer, nullable=True, default=0)
    def set_password(self, password):
        self.password = password
        
    def check_password(self, password):
        return password == self.password

    def to_dict(self):
        return {"id": self.id, "name": self.name, "username": self.username, "role": self.role, "version": self.version}

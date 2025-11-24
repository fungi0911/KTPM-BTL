from typing import List, Optional
from app.extensions import db
from app.models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, session=None):
        self.session = session or db.session

    def get_by_id(self, id: int) -> Optional[User]:
        return self.session.get(User, id)

    def list(self, **kwargs) -> List[User]:
        return self.session.query(User).all()

    def create(self, data: dict) -> User:
        u = User(**data)
        if 'password' in data:
            u.set_password(data['password'])
        self.session.add(u)
        self.session.commit()
        return u

    def update(self, id: int, data: dict) -> Optional[User]:
        u = self.get_by_id(id)
        if not u:
            return None
        if 'name' in data:
            u.name = data['name']
        if 'role' in data:
            u.role = data['role']
        if 'password' in data:
            u.set_password(data['password'])
        self.session.commit()
        return u

    def delete(self, id: int) -> bool:
        u = self.get_by_id(id)
        if not u:
            return False
        self.session.delete(u)
        self.session.commit()
        return True

    def find_by_username(self, username: str) -> Optional[User]:
        return self.session.query(User).filter_by(username=username).first()

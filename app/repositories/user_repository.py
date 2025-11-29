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
        from app.utils.occ import occ_execute
        read_sql = "SELECT COALESCE(version,0) AS version FROM users WHERE id = :id"
        read_params = { 'id': id }

        def build_update(expected_version: int):
            set_parts = []
            params = { 'id': id, 'expected_version': expected_version, 'new_version': expected_version + 1 }
            if 'name' in data and data['name'] is not None:
                set_parts.append('name = :name')
                params['name'] = data['name']
            if 'role' in data and data['role'] is not None:
                set_parts.append('role = :role')
                params['role'] = data['role']
            if 'password' in data and data['password'] is not None:
                # keep plain assignment semantics per existing logic
                set_parts.append('password = :password')
                params['password'] = data['password']
            set_parts.append('version = :new_version')
            set_clause = ', '.join(set_parts) if set_parts else 'version = :new_version'
            update_sql = f"""
                UPDATE users
                SET {set_clause}
                WHERE id = :id AND (version = :expected_version OR version IS NULL)
            """
            return update_sql, params

        ok = occ_execute(read_sql, read_params, build_update, session=self.session, max_retries=5, commit=True)
        if not ok:
            return None
        return self.session.get(User, id)

    def delete(self, id: int) -> bool:
        u = self.get_by_id(id)
        if not u:
            return False
        self.session.delete(u)
        self.session.commit()
        return True

    def find_by_username(self, username: str) -> Optional[User]:
        return self.session.query(User).filter_by(username=username).first()

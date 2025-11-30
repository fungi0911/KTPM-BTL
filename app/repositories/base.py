from abc import ABC, abstractmethod


class BaseRepository(ABC):
    @abstractmethod
    def get_by_id(self, id):
        raise NotImplementedError

    @abstractmethod
    def list(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def create(self, data):
        raise NotImplementedError

    @abstractmethod
    def update(self, id, data):
        raise NotImplementedError

    @abstractmethod
    def delete(self, id):
        raise NotImplementedError

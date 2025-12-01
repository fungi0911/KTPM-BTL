from fastapi_app import create_app
from fastapi_app.database import Base, engine
from fastapi_app.models import *  # noqa: F401,F403 ensure models imported for metadata

app = create_app()

# Create tables at startup if not exist (development convenience)
@app.on_event("startup")
def _create_tables():
    if engine is not None:
        Base.metadata.create_all(bind=engine)

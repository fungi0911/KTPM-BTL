from app.celery_app import celery
from run import app

if __name__ == "__main__":
    with app.app_context():
        celery.worker_main()

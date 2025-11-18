from celery import Celery

celery = Celery(
    "app",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)

def init_celery(app):
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery
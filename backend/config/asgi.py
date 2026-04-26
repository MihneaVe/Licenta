from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_mood_meter.backend.config.settings')

application = get_asgi_application()
from django.apps import AppConfig


class BuildingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'buildings'

    def ready(self):
        """Connect signal handlers when the app is fully loaded."""
        import buildings.signals  # noqa: F401

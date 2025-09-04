from django.apps import AppConfig


class DeliveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'delivery'
    
    def ready(self):
        """Import signal handlers when the app is ready"""
        import delivery.integration  # This will register the signal handlers

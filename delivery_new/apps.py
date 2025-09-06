from django.apps import AppConfig


class DeliveryNewConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'delivery_new'
    verbose_name = 'Delivery System'
    
    def ready(self):
        # Import signals
        import delivery_new.signals

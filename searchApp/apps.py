from django.apps import AppConfig


class SearchappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'searchApp'

    def ready(self):
        from django.apps import apps

        for model in apps.get_models():
            if not model._meta.db_table:
                model._meta.db_table = model._meta.model_name.lower()

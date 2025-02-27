from django.apps import AppConfig


class SearchappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'searchApp'


class LowercaseTableNameAppConfig(AppConfig):
    name = 'searchApp'

    def ready(self):
        from django.db.models.signals import class_prepared

        def make_lowercase(sender, **kwargs):
            if sender._meta.app_label == self.label:
                sender._meta.db_table = sender._meta.db_table.lower()

        class_prepared.connect(make_lowercase)

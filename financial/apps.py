# =============================================================================
# financial/apps.py
# =============================================================================

from django.apps import AppConfig


class FinancialConfig(AppConfig):
    name = "financial"
    verbose_name = "Finance"

    def ready(self):
        import financial.signals  # noqa: F401

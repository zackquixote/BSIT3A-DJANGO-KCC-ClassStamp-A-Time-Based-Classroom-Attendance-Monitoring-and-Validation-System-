import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        import apps.core.signals
        self._refresh_bundles()

    @staticmethod
    def _refresh_bundles():
        # A failed rebuild must not stop the site from booting: the bundles
        # committed in static/ still serve, and the error is logged instead.
        try:
            from apps.core.services import asset_bundles
            rebuilt = asset_bundles.build_if_stale()
        except Exception:
            logger.exception('static bundle rebuild skipped')
            return
        if rebuilt:
            logger.info('rebuilt static bundles: %s', ', '.join(rebuilt))

"""Celery app trace module."""


class TraceBuilder:
    """Trace builder for celery tasks."""

    def __init__(self, app):
        self.app = app

    def build_tracer(self, task):
        """Build tracer method."""
        return self.app.trace

    async def async_build_tracer(self, task):
        """Async build tracer method."""
        return self.app.trace

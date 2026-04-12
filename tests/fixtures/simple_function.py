"""Simple Celery task example."""


def build_tracer(app, name, loader=None):
    """Build a tracer for a task."""
    return app.trace


async def async_build_tracer(app, name):
    """Async tracer builder."""
    return app.trace

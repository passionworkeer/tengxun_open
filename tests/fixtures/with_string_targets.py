"""Module with string target paths for dynamic imports."""

# Dynamic import targets
TRACE_TARGET = "celery.app.trace.build_tracer"
ASYNC_TARGET = "celery.decorators.async_task"

# String literal with dot-separated path
TASK_PATH = "celery.app.base:task_from_fun"

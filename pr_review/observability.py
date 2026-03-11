"""Langfuse observability integration.

Tracing architecture:
  - Each LLM node decorates itself with @observe(name="node_name").
  - trace_invoke() wraps the full graph run as a root @observe trace so
    all node spans are grouped under one trace in the Langfuse dashboard.
  - get_langchain_handler() returns a CallbackHandler pinned to the current
    @observe span so LangChain LLM calls appear as child generations with
    prompt, completion, token counts, and latency.

Usage in a node:
    from pr_review.observability import get_langchain_handler, langfuse_context, observe

    @observe(name="my_node")
    def my_node(state):
        handler = get_langchain_handler()
        config = {"callbacks": [handler]} if handler else {}
        result = structured_llm.invoke([...], config=config)

Tracing is optional: if langfuse is not installed or LANGFUSE_PUBLIC_KEY is
not set, all helpers become no-ops and the pipeline runs normally.
"""

import logging
import os
import urllib.request
import urllib.error
from typing import Callable

logger = logging.getLogger("pr_review.observability")

# ---------------------------------------------------------------------------
# Safe imports — provide no-op stubs when langfuse is not installed
# ---------------------------------------------------------------------------
try:
    from langfuse.decorators import langfuse_context, observe  # type: ignore[import]
    _langfuse_installed = True
except ImportError:
    _langfuse_installed = False
    logger.debug("langfuse package not installed — tracing stubs active")

    def observe(*args, **kwargs):  # type: ignore[misc]
        """No-op decorator used when langfuse is not installed."""
        _ = args, kwargs
        def decorator(fn: Callable) -> Callable:
            return fn
        return decorator

    class _NoOpCtx:
        def get_current_trace_id(self) -> None:
            return None

        def get_current_observation_id(self) -> None:
            return None

        def get_current_langchain_handler(self) -> None:
            return None

    langfuse_context = _NoOpCtx()  # type: ignore[assignment]


def _langfuse_reachable(host: str, timeout: float = 2.0) -> bool:
    """Return True if the Langfuse host responds to a HEAD request."""
    try:
        urllib.request.urlopen(host, timeout=timeout)  # noqa: S310
        return True
    except urllib.error.URLError:
        return False
    except Exception:
        return False


def setup_langfuse() -> None:
    """Log Langfuse configuration status at startup.

    If the Langfuse host is unreachable (e.g. Docker is down), clears
    LANGFUSE_PUBLIC_KEY so the rest of the pipeline treats tracing as disabled
    and the Langfuse SDK never attempts to flush — suppressing connection errors.
    """
    if not _langfuse_installed:
        logger.info("langfuse package not installed — tracing disabled.")
        return
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        logger.info(
            "LANGFUSE_PUBLIC_KEY not set — tracing disabled "
            "(set key + restart to enable)."
        )
        return

    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    if not _langfuse_reachable(host):
        logger.warning(
            "Langfuse host unreachable (%s) — tracing disabled for this run.", host
        )
        os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
        return

    logger.debug("Langfuse tracing enabled → %s", host)


def trace_invoke(graph: object, state: dict, *, name: str = "pr-review") -> dict:
    """Invoke graph.invoke(state) inside a single Langfuse root trace.

    All nested @observe node spans and their LangChain generations appear as
    children of this trace in the Langfuse dashboard.
    """
    @observe(name=name)
    def _invoke() -> dict:
        return graph.invoke(state)  # type: ignore[union-attr]

    return _invoke()


def get_langchain_handler():
    """Return a LangChain CallbackHandler nested under the current @observe span.

    Pass the returned handler to structured_llm.invoke(config={"callbacks": [h]})
    so LLM generations appear as children of the enclosing node span.
    Returns None when tracing is not configured (invoke proceeds without tracing).
    """
    if not _langfuse_installed or not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        return None
    try:
        return langfuse_context.get_current_langchain_handler()
    except Exception as exc:
        logger.warning("Failed to create Langfuse CallbackHandler: %s", exc)
        return None

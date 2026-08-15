"""ASGI entrypoint: ``uvicorn evalforge_api.asgi:app``.

Importing this module constructs and validates ``Settings`` immediately,
so invalid or missing sensitive configuration fails process startup
rather than failing on the first request.
"""

from __future__ import annotations

from evalforge_api.app import create_app

app = create_app()

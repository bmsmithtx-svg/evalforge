"""Port interfaces that domain and application code depend on.

Adapters under ``evalforge_api.adapters`` implement these protocols.
Nothing in this package may import a concrete adapter, FastAPI, or a
provider client — dependencies point inward per the architecture's
allowed dependency direction.
"""

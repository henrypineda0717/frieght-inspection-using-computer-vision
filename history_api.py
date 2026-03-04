"""
Compatibility wrapper for old app.py
Redirects to new backend structure
"""

def _get_router():
    """Lazy import to avoid circular dependency"""
    from backend.app.api.history import router
    return router

# Create a property-like access
class RouterProxy:
    @property
    def router(self):
        return _get_router()

_proxy = RouterProxy()
router = _proxy.router

__all__ = ["router"]

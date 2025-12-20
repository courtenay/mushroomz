"""Shared scene state - avoids circular imports."""

# Shared flag to suppress other displays when manual is active
_manual_active = False


def is_manual_active() -> bool:
    """Check if manual scene is currently active."""
    return _manual_active


def set_manual_active(active: bool) -> None:
    """Set whether manual scene is active."""
    global _manual_active
    _manual_active = active

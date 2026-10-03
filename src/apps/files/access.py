"""Per-target read authorization for attachments. A module that attaches files to its own model registers a
checker ``(membership, target) -> bool`` so downloads honour that module's rules (for example site scope).
Targets without a checker fall back to the attachment's ``read_permission`` (organization-wide)."""
from collections.abc import Callable

_CHECKERS: dict[str, Callable] = {}


def register(model_label: str, checker: Callable) -> None:
    _CHECKERS[model_label.lower()] = checker


def checker_for(model_label: str) -> Callable | None:
    return _CHECKERS.get(model_label.lower())

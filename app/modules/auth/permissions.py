import re

_NAME = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")
_declared: set[str] = set()
_everyone: set[str] = set()


def permission(name: str, everyone: bool = False) -> str:
    """Declare a permission as "<area>.<action>" and return its name. ``everyone``: it
    may be given to the role of every new account (an action of the user area)."""
    if not _NAME.fullmatch(name):
        raise ValueError(f"Permission name must look like 'area.action': {name!r}")
    _declared.add(name)
    if everyone:
        _everyone.add(name)
    return name


def all_permissions() -> frozenset[str]:
    return frozenset(_declared)


def everyone_permissions() -> frozenset[str]:
    return frozenset(_everyone)


def check_declared(*names: str) -> None:
    if unknown := [name for name in names if name not in _declared]:
        raise ValueError(f"Unknown permission: {', '.join(unknown)}")


ADMIN_ACCESS = permission("admin.access")

from typing import Any

from app.core.i18n import translate, translate_optional


def render(kind: str, params: dict[str, Any], language: str | None = None) -> tuple[str, str]:
    title = translate_optional(f"notifications.{kind}.title", language, **params)
    if title is None:
        return kind, ""
    return title, translate(f"notifications.{kind}.body", language, **params)

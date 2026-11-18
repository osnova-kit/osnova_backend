from typing import ClassVar

from pydantic import ConfigDict

from app.core.settings.base import Described


class EntityType(Described):
    model_config = ConfigDict(extra="ignore")

    type: ClassVar[str]
    group: ClassVar[str]


entity_types: dict[str, type[EntityType]] = {}


def entity_type[E: type[EntityType]](cls: E) -> E:
    """Class decorator: make an entity type available to the admin."""
    entity_types[cls.type] = cls
    return cls

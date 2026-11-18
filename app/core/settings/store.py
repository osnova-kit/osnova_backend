from app.core.settings.base import SettingsGroup


class SettingsStore:
    def __init__(self) -> None:
        self._values: dict[str, SettingsGroup] = {}

    def get[G: SettingsGroup](self, group: type[G]) -> G:
        value = self._values.get(group.group)
        if not isinstance(value, group):
            value = group()
            self._values[group.group] = value
        return value

    def set(self, value: SettingsGroup) -> None:
        self._values[value.group] = value

    def reset(self) -> None:
        self._values.clear()


settings = SettingsStore()

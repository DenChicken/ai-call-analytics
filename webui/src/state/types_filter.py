import reflex as rx

from src import context, urlstate
from src.constants import PARAM_TYPES, TYPES_SUMMARY_TEMPLATE
from src.database import CallType


class TypesFilterState(rx.State, mixin=True):
    available_types: list[CallType] = []
    selected_types: list[str] = []
    filter_menu_open: bool = False

    @rx.var
    def types_summary(self) -> str:
        return TYPES_SUMMARY_TEMPLATE.format(
            selected=len(self.selected_types), total=len(self.available_types)
        )

    @rx.event
    def toggle_type(self, code: str, enabled: bool):
        codes = {str(entry) for entry in self.selected_types}
        if enabled:
            codes.add(code)
        else:
            codes.discard(code)
        self.selected_types = [
            entry.code for entry in self.available_types if entry.code in codes
        ]

    @rx.event
    def apply_types(self, is_open: bool):
        self.filter_menu_open = is_open
        if is_open:
            return
        return self._types_changed()

    def _load_types(self) -> None:
        if self.available_types:
            return
        self.available_types = [
            CallType(code=row["code"], label=row["label"])
            for row in context.database().call_types()
        ]
        self.selected_types = [entry.code for entry in self.available_types]

    def _read_types(self, params) -> None:
        self.selected_types = urlstate.read_list(
            params, PARAM_TYPES, self._type_codes, self.selected_types
        )

    @property
    def _type_codes(self) -> list[str]:
        return [entry.code for entry in self.available_types]

    @property
    def _types_param(self) -> str:
        return urlstate.write_list(self.selected_types, self._type_codes)

import reflex as rx

from src import urlstate
from src.constants import (
    DEFAULT_PERIOD,
    PARAM_PERIOD,
    PERIOD_BY_CODE,
    PERIOD_BY_LABEL,
)


class PeriodFilterState(rx.State, mixin=True):
    period: str = DEFAULT_PERIOD

    @rx.var
    def period_label(self) -> str:
        return PERIOD_BY_CODE[self.period].label

    @rx.event
    def set_period(self, label: str):
        self.period = PERIOD_BY_LABEL.get(label, self.period)
        return self._period_changed()

    def _read_period(self, params) -> None:
        self.period = urlstate.read_choice(
            params, PARAM_PERIOD, PERIOD_BY_CODE, self.period
        )

    @property
    def _auto_refresh(self) -> bool:
        return PERIOD_BY_CODE[self.period].auto_refresh

import reflex as rx

from src import urlstate
from src.constants import (
    PARAM_PERIOD,
    PERIOD_BY_CODE,
    PERIOD_BY_LABEL,
    PERIOD_TODAY,
)


class PeriodFilterState(rx.State, mixin=True):
    period: str = PERIOD_TODAY

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

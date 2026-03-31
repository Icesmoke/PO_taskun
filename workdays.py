import datetime as dt
from functools import lru_cache
from typing import Iterable, Optional, Set

import holidays


@lru_cache(maxsize=32)
def _ru_holidays_for_year(year: int) -> Set[dt.date]:
    ru = holidays.RU(years=[year])
    return {d for d in ru.keys()}


def ru_holidays_for_years(years: Iterable[int]) -> Set[dt.date]:
    out: Set[dt.date] = set()
    for y in years:
        out |= _ru_holidays_for_year(int(y))
    return out


class WorkdayCalendar:
    """
    Workdays = Mon..Fri excluding holidays (RU).
    """

    def __init__(self, *, holiday_dates: Set[dt.date]):
        self._holidays = holiday_dates

    def is_workday(self, d: dt.date) -> bool:
        if d.weekday() >= 5:
            return False
        if d in self._holidays:
            return False
        return True

    def workdays_inclusive(self, start: dt.date, end: dt.date) -> Set[dt.date]:
        if start > end:
            return set()
        out: Set[dt.date] = set()
        cur = start
        while cur <= end:
            if self.is_workday(cur):
                out.add(cur)
            cur += dt.timedelta(days=1)
        return out


def calendar_for_period(start: dt.date, end: dt.date) -> WorkdayCalendar:
    years = range(start.year, end.year + 1)
    return WorkdayCalendar(holiday_dates=ru_holidays_for_years(years))


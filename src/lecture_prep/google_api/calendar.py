"""Read events from Google Calendar through the Calendar REST API (v3).

Exercise: `events_on` is yours to implement - see tests/test_google_calendar.py for the spec.
`drive.py` in this folder is a good model: same httpx client, same BearerAuth, same pagination idea.
"""

from dataclasses import dataclass
from datetime import date, datetime
from types import TracebackType
from typing import Self
from zoneinfo import ZoneInfo

import httpx

from lecture_prep.config import Settings
from lecture_prep.google_api.auth import BearerAuth, TokenSource

CALENDAR_URL = "https://www.googleapis.com/calendar/v3"


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    title: str  # the event's "summary" in Google's terms; "" when the event has no title
    start: datetime  # timezone-aware
    end: datetime  # timezone-aware


class CalendarClient:
    """Thin wrapper over the Calendar API. Takes an httpx.Client so tests can plug in a fake transport."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        http = httpx.Client(
            base_url=CALENDAR_URL, auth=BearerAuth(TokenSource(settings.google_token_path)), timeout=30
        )
        return cls(http)

    def events_on(self, day: date, tz: ZoneInfo) -> list[CalendarEvent]:
        """Return the timed events of `day` (midnight to midnight in `tz`) from the primary calendar.

        Ordered by start time. All-day events (no specific hour) are skipped - lectures have hours.
        """
        raise NotImplementedError("Task 2 - yours to write")

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

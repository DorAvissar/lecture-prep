"""Read events from Google Calendar through the Calendar REST API (v3)."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote
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

    def __init__(self, http: httpx.Client, calendar_ids: tuple[str, ...] = ("primary",)) -> None:
        self._http = http
        # "primary" is your own calendar; shared calendars (a university one) are added by their id.
        self._calendar_ids = calendar_ids

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        http = httpx.Client(
            base_url=CALENDAR_URL, auth=BearerAuth(TokenSource(settings.google_token_path)), timeout=30
        )
        return cls(http, tuple(settings.calendar_ids))

    def events_on(self, day: date, tz: ZoneInfo) -> list[CalendarEvent]:
        """Return the timed events of `day` (midnight to midnight in `tz`) from every configured calendar.

        Ordered by start time. All-day events (no specific hour) are skipped - lectures have hours.
        """
        events = [event for calendar_id in self._calendar_ids for event in self._events(calendar_id, day, tz)]
        return sorted(events, key=lambda event: event.start)

    def _events(self, calendar_id: str, day: date, tz: ZoneInfo) -> list[CalendarEvent]:
        day_start = datetime.combine(day, time(), tzinfo=tz)
        params = {
            "timeMin": day_start.isoformat(),
            "timeMax": (day_start + timedelta(days=1)).isoformat(),
            "singleEvents": "true",  # expand repeating events (a weekly lecture) into single occurrences
            "orderBy": "startTime",  # only allowed together with singleEvents
        }
        events: list[CalendarEvent] = []
        while True:  # Google returns long result lists in pages, linked by nextPageToken
            response = self._http.get(f"/calendars/{quote(calendar_id, safe='')}/events", params=params)
            response.raise_for_status()
            page = response.json()
            events.extend(_to_event(raw) for raw in page.get("items", []) if "dateTime" in raw["start"])
            if "nextPageToken" not in page:
                return events
            params["pageToken"] = page["nextPageToken"]

    def calendars(self) -> list[tuple[str, str]]:
        """(id, name) of every calendar in your list, including ones shared with you."""
        response = self._http.get("/users/me/calendarList")
        response.raise_for_status()
        return [(raw["id"], raw.get("summary", "")) for raw in response.json().get("items", [])]

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()


def _to_event(raw: dict[str, Any]) -> CalendarEvent:
    return CalendarEvent(
        id=raw["id"],
        title=raw.get("summary", ""),  # Google leaves "summary" out when the event has no title
        start=datetime.fromisoformat(raw["start"]["dateTime"]),
        end=datetime.fromisoformat(raw["end"]["dateTime"]),
    )

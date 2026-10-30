"""Spec for Task 2 (CalendarClient.events_on). httpx.MockTransport plays the role of Google Calendar."""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from lecture_prep.google_api.auth import BearerAuth
from lecture_prep.google_api.calendar import CALENDAR_URL, CalendarClient, CalendarEvent

TZ = ZoneInfo("Asia/Jerusalem")
DAY = date(2026, 11, 2)

Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler, calendar_ids: tuple[str, ...] = ("primary",)) -> CalendarClient:
    http = httpx.Client(
        base_url=CALENDAR_URL, transport=httpx.MockTransport(handler), auth=BearerAuth(lambda: "test-token")
    )
    return CalendarClient(http, calendar_ids)


def timed_event(event_id: str, title: str, start: str, end: str) -> dict:
    return {"id": event_id, "summary": title, "start": {"dateTime": start}, "end": {"dateTime": end}}


def events(*items: dict, next_page: str | None = None) -> httpx.Response:
    body: dict = {"items": list(items)}
    if next_page:
        body["nextPageToken"] = next_page
    return httpx.Response(200, json=body)


def test_asks_the_primary_calendar_for_one_local_day():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return events()

    make_client(handler).events_on(DAY, TZ)

    [request] = seen
    params = request.url.params
    assert request.url.path == "/calendar/v3/calendars/primary/events"
    assert request.headers["Authorization"] == "Bearer test-token"
    assert datetime.fromisoformat(params["timeMin"]) == datetime(2026, 11, 2, tzinfo=TZ)
    assert datetime.fromisoformat(params["timeMax"]) == datetime(2026, 11, 3, tzinfo=TZ)
    assert params["singleEvents"] == "true"  # expand weekly repeating lectures into single events
    assert params["orderBy"] == "startTime"


def test_parses_timed_events():
    def handler(request: httpx.Request) -> httpx.Response:
        return events(
            timed_event("e1", "לינארית - הרצאה", "2026-11-02T10:00:00+02:00", "2026-11-02T12:00:00+02:00")
        )

    [event] = make_client(handler).events_on(DAY, TZ)

    assert event == CalendarEvent(
        id="e1",
        title="לינארית - הרצאה",
        start=datetime(2026, 11, 2, 10, tzinfo=TZ),
        end=datetime(2026, 11, 2, 12, tzinfo=TZ),
    )


def test_skips_all_day_events():
    all_day = {
        "id": "e0",
        "summary": "יום הולדת",
        "start": {"date": "2026-11-02"},
        "end": {"date": "2026-11-03"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        lecture = timed_event(
            "e1", "Data Structures", "2026-11-02T09:00:00+02:00", "2026-11-02T11:00:00+02:00"
        )
        return events(all_day, lecture)

    assert [event.id for event in make_client(handler).events_on(DAY, TZ)] == ["e1"]


def test_event_without_a_title_gets_an_empty_title():
    def handler(request: httpx.Request) -> httpx.Response:
        untitled = timed_event("e1", "", "2026-11-02T09:00:00+02:00", "2026-11-02T10:00:00+02:00")
        del untitled["summary"]  # Google leaves the field out entirely
        return events(untitled)

    [event] = make_client(handler).events_on(DAY, TZ)

    assert event.title == ""


def test_follows_pagination():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("pageToken") == "page-2":
            return events(timed_event("e2", "B", "2026-11-02T14:00:00+02:00", "2026-11-02T15:00:00+02:00"))
        return events(
            timed_event("e1", "A", "2026-11-02T09:00:00+02:00", "2026-11-02T10:00:00+02:00"),
            next_page="page-2",
        )

    assert [event.id for event in make_client(handler).events_on(DAY, TZ)] == ["e1", "e2"]


def test_merges_several_calendars_by_start_time():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.raw_path.decode().split("?")[0])
        if "primary" in request.url.path:
            return events(
                timed_event("p1", "Dentist", "2026-11-02T12:00:00+02:00", "2026-11-02T13:00:00+02:00")
            )
        return events(timed_event("u1", "חדוא 2", "2026-11-02T09:00:00+02:00", "2026-11-02T11:00:00+02:00"))

    uni = "abc#uni@group.calendar.google.com"
    found = make_client(handler, ("primary", uni)).events_on(DAY, TZ)

    assert [event.id for event in found] == ["u1", "p1"]
    assert paths == [
        "/calendar/v3/calendars/primary/events",
        "/calendar/v3/calendars/abc%23uni%40group.calendar.google.com/events",
    ]


def test_lists_the_calendars_you_can_read():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/calendar/v3/users/me/calendarList"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": "me@gmail.com", "summary": "me@gmail.com", "primary": True},
                    {"id": "uni@group.calendar.google.com", "summary": "Lectures"},
                ]
            },
        )

    assert make_client(handler).calendars() == [
        ("me@gmail.com", "me@gmail.com"),
        ("uni@group.calendar.google.com", "Lectures"),
    ]

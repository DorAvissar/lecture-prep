"""Print the calendars your Google account can read, to find the id of a shared calendar:

    uv run python -m lecture_prep.google_api.calendars

Put the ids to read lectures from in .env, e.g. CALENDAR_IDS=["primary", "<id>"].
"""

from lecture_prep.config import get_settings
from lecture_prep.google_api.calendar import CalendarClient


def main() -> None:
    with CalendarClient.from_settings(get_settings()) as calendar:
        for calendar_id, name in calendar.calendars():
            print(name)
            print(f"    {calendar_id}")


if __name__ == "__main__":
    main()

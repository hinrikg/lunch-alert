from datetime import date, datetime
from dateutil.tz import UTC
from icalevents import icalevents
import os
import re
import requests


LUNCH_CALENDAR_URL = os.environ["LUNCH_CALENDAR_URL"]
HOLIDAY_CALENDAR_URL = os.environ["HOLIDAY_CALENDAR_URL"]
SLACK_URL = os.environ["SLACK_URL"]

HOLIDAY_MESSAGE_TEMPLATE = ":parrot: Happy {}!"

LUNCH_MESSAGE_TEMPLATE = "<!here> It's lunchtime! Today we're having {}"

UNKNOWN_LUNCH_MESSAGE = (
    "<!here> It's lunchtime! But unfortunately I can't read the menu for you today "
    ":weary:"
)


def main():
    if is_the_weekend():
        return

    holiday_event = fetch_holiday_event()
    lunch_event = fetch_lunch_event()
    if holiday_event:
        send_holiday_message(holiday_event)
    elif lunch_event:
        send_lunch_message(lunch_event)
    else:
        send_unknown_lunch_message()


def is_the_weekend():
    return datetime.utcnow().isoweekday() >= 6


def fetch_lunch_event():
    events = fetch_events_today(LUNCH_CALENDAR_URL)

    # Filter out the breakfast entry which usually has the summary "1. <description>"
    events = list(filter(lambda e: not e.summary.startswith("1."), events))

    # The lunch summary is usually of the form "2. <description>"
    for event in events:
        if event.summary.startswith("2."):
            return event

    # Otherwise let's sort the menu by the the absolute delta time from now and use the
    # event that's closest
    events = sorted(events, key=lambda e: delta_from_now(e.start))
    if events:
        return events[0]


def delta_from_now(dt):
    now = datetime.utcnow()
    return abs(now.astimezone(UTC) - dt.astimezone(UTC))


def fetch_holiday_event():
    events = fetch_events_today(HOLIDAY_CALENDAR_URL)
    # let's just naively use the first available entry
    return events[0] if events else None


def fetch_events_today(url):
    # for some reason icalevents thinks it's cute to return all-day events from the
    # day before (and sometimes after) the requested start date, so we need to filter
    # those out manually.
    return [
        event
        for event in icalevents.events(url, start=date.today())
        if event.start.date() == date.today()
    ]


def send_holiday_message(event):
    send_message(HOLIDAY_MESSAGE_TEMPLATE.format(event.summary))


def send_lunch_message(event):
    summary = get_lunch_summary(event)
    text = LUNCH_MESSAGE_TEMPLATE.format(summary)
    send_message(text)


def get_lunch_summary(event):
    summary = event.summary
    match = re.match(r"(?:\d+\.?)?(?P<summary>.*)", summary)
    if match:
        summary = match.group("summary").strip()
    return summary


def send_unknown_lunch_message():
    send_message(UNKNOWN_LUNCH_MESSAGE)


def send_message(text):
    requests.post(SLACK_URL, json={"text": text})


if __name__ == "__main__":
    main()

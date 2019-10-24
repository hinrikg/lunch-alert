from datetime import date, datetime, time, timedelta
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
    if holiday_event:
        send_holiday_message(holiday_event)

    lunch_event = fetch_lunch_event()
    if lunch_event:
        send_lunch_message(lunch_event)
    else:
        send_unknown_lunch_message()


def is_the_weekend():
    return datetime.utcnow().isoweekday() >= 6


def fetch_lunch_event():
    events = fetch_events_today(LUNCH_CALENDAR_URL)
    if not events:
        return None

    # Breakfast usually has the summary "1. <breakfast description>" so let's start by
    # removing that entry
    events = list(filter(lambda event: not event.summary.startswith("1."), events))
    if not events:
        return None

    # The lunch summary is usually of the form "2. <lunch description>" so let's see if
    # we can find the right entry easily
    for event in events:
        if event.summary.startswith("2."):
            return event

    # Otherwise let's sort the menu by the the absolute delta from now and use the
    # event that's closest
    return sorted(events, key=lambda e: delta_from_now(e.start))[0]


def delta_from_now(dt):
    now = datetime.utcnow()
    return abs(now.astimezone(UTC) - dt.astimezone(UTC))


def fetch_holiday_event():
    events = fetch_events_today(HOLIDAY_CALENDAR_URL)
    # let's just naively use the first available entry
    return events[0] if events else None


def fetch_events_today(url):
    # for some reason icalevents thinks it's cute to return all-day events from the
    # day before the requested start date, so we need to forcefully make sure that the
    # start and end parameters are defined 'within' today.
    start = date.today() + timedelta(seconds=1)
    end = date.today() + timedelta(days=1) - timedelta(seconds=1)
    return icalevents.events(url, start=start, end=end)


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
    else:
        print("failed to parse menu entry")
    return summary


def send_unknown_lunch_message():
    send_message(UNKNOWN_LUNCH_MESSAGE)


def send_message(text):
    requests.post(SLACK_URL, json={"text": text})


if __name__ == "__main__":
    main()

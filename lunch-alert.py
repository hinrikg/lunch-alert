from datetime import datetime
from icalevents import icalevents
import os
import re
import requests


CALENDAR_URL = os.environ["CALENDAR_URL"]
SLACK_URL = os.environ["SLACK_URL"]

LUNCH_MESSAGE_TEMPLATE = "<!here> It's lunchtime! Today we're having {}"

UNKNOWN_LUNCH_MESSAGE = "<!here> It's lunchtime! But unfortunately I can't read the menu for you today :weary:"


def main():
    if is_the_weekend():
        return

    lunch_event = fetch_lunch_event()
    if lunch_event:
        send_lunch_message(lunch_event)
    else:
        send_unknown_lunch_message()


def is_the_weekend():
    return datetime.utcnow().isoweekday() >= 6


def fetch_lunch_event():
    events = fetch_events()
    if len(events) == 0:
        return None
    events = sorted(events, key=lambda e: e.summary)
    return events[-1]


def fetch_events():
    now = datetime.utcnow()
    return icalevents.events(CALENDAR_URL, start=now, end=now)


def send_lunch_message(event):
    summary = get_lunch_summary(event)
    text = LUNCH_MESSAGE_TEMPLATE.format(summary)
    send_message(text)


def get_lunch_summary(event):
    summary = event.summary
    match = re.match(r"(?:\d+\.?)?(?P<summary>.*)", summary)
    if match:
        summary = match.group('summary').strip()
    else:
        print "failed to parse menu entry"
    return summary


def send_unknown_lunch_message():
    send_message(UNKNOWN_LUNCH_MESSAGE)


def send_message(text):
    requests.post(SLACK_URL, json={"text": text})


if __name__ == "__main__":
    main()

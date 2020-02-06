from datetime import date, datetime
import logging
import os
import re

from dateutil.tz import UTC
from icalevents import icalevents
import requests
import timber


TIMBER_API_KEY = os.environ.get("TIMBER_API_KEY", None)
TIMBER_SOURCE_ID = os.environ.get("TIMBER_SOURCE_ID", None)

LUNCH_CALENDAR_URL = os.environ["LUNCH_CALENDAR_URL"]
HOLIDAY_CALENDAR_URL = os.environ["HOLIDAY_CALENDAR_URL"]
SLACK_URL = os.environ["SLACK_URL"]

HOLIDAY_MESSAGE_TEMPLATE = ":parrot: Happy {}!"

LUNCH_MESSAGE_TEMPLATE = "<!here> It's lunchtime! Today we're having {}"

UNKNOWN_LUNCH_MESSAGE = (
    "<!here> It's lunchtime! But unfortunately I can't read the menu for you today "
    ":weary:"
)


logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

if TIMBER_API_KEY and TIMBER_SOURCE_ID:
    timber_handler = timber.TimberHandler(
        source_id=TIMBER_SOURCE_ID, api_key=TIMBER_API_KEY
    )
    logger.addHandler(timber_handler)


def main():
    logger.info("starting")

    if is_the_weekend():
        logger.info("stopping - it's the weekend")
        return

    holiday_event = fetch_holiday_event()
    lunch_event = fetch_lunch_event()
    if holiday_event:
        send_holiday_message(holiday_event)
    elif lunch_event:
        send_lunch_message(lunch_event)
    else:
        logger.info("no event found - sending")
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
    logger.info("fetch_events_today %s", url)
    events = [
        event
        for event in _fetch_events_with_retry(url, start=date.today())
        if event.start.date() == date.today()
    ]
    logger.info("found %s events:", len(events))
    for i, event in enumerate(events):
        logger.info("%s: %s", i, event)
    return events


def _fetch_events_with_retry(url, start, retries=3):
    attempts = 0
    fetched_events = None
    while fetched_events is None and attempts <= retries:
        try:
            fetched_events = icalevents.events(url, start=start)
        except TimeoutError:
            logger.warning("request timed out")
            attempts += 1
            if attempts > retries:
                logger.error("giving up after %s retries", retries)
                raise
    return fetched_events


def send_holiday_message(event):
    logger.info("send_holiday_message %s", event)
    send_message(HOLIDAY_MESSAGE_TEMPLATE.format(event.summary))


def send_lunch_message(event):
    logger.info("send_lunch_message %s", event)
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
    logger.info("send_message %s", text)
    requests.post(SLACK_URL, json={"text": text})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Uncaught exception")

import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
CST = pytz.timezone("America/Chicago")

class Scheduler:
    def __init__(self):
        self._last_morning_brief_date = None
        self._last_eod_report_date = None
        self._last_checkin_hour = None

    def check(self) -> str | None:
        now = datetime.now(CST)
        today = now.date()
        hour = now.hour
        minute = now.minute

        if hour == 9 and minute == 15:
            if self._last_morning_brief_date != today:
                self._last_morning_brief_date = today
                return "morning_brief"

        if hour == 16 and minute == 30:
            if self._last_eod_report_date != today:
                self._last_eod_report_date = today
                return "eod_report"

        if 10 <= hour <= 15 and minute == 0:
            if self._last_checkin_hour != (today, hour):
                self._last_checkin_hour = (today, hour)
                return "checkin"

        return None

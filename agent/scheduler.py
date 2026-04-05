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
        self._last_weekend_greeting_date = None
        self._last_signal_scan_date = None
        self._user_active_today = False
        self._user_active_date = None

    def mark_user_active_today(self):
        """Called from handle_message on weekends to suppress auto-greeting."""
        today = datetime.now(CST).date()
        self._user_active_today = True
        self._user_active_date = today

    def _is_user_active_today(self) -> bool:
        today = datetime.now(CST).date()
        if self._user_active_date != today:
            self._user_active_today = False
            self._user_active_date = None
        return self._user_active_today

    def check(self) -> str | None:
        now = datetime.now(CST)
        today = now.date()
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()  # 0=Mon, 5=Sat, 6=Sun

        # ── Weekend schedule ──
        if weekday == 5:  # Saturday
            if hour == 11 and minute == 0:
                if self._last_weekend_greeting_date != today and not self._is_user_active_today():
                    self._last_weekend_greeting_date = today
                    return "weekend_greeting"
            return None

        if weekday == 6:  # Sunday
            if hour == 13 and minute == 0:
                if self._last_weekend_greeting_date != today and not self._is_user_active_today():
                    self._last_weekend_greeting_date = today
                    return "weekend_greeting"
            return None

        # ── Weekday schedule (Mon-Fri) ──
        if hour == 7 and minute == 45:
            if self._last_signal_scan_date != today:
                self._last_signal_scan_date = today
                return "signal_scan"

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

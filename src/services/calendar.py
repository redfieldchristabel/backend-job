from datetime import date, timedelta
import holidays

class CalendarService:
    def __init__(self, state: str = "KUL"):
        """
        Initializes the dynamic Malaysian Holiday calendar.
        Default state code is set to 'KUL' (Kuala Lumpur).
        """
        self.state = state
        # Create the dynamic holiday lookup object for Malaysia
        self.my_holidays = holidays.Malaysia(state=self.state)

    def is_weekend(self, check_date: date) -> bool:
        """Returns True if the date falls on a Saturday (5) or Sunday (6)."""
        # Note: If adapting for Johor, Kedah, Kelantan, or Terengganu, 
        # the weekends are Friday (4) and Saturday (5).
        if self.state in ["JHR", "KDH", "KTN", "TRG"]:
            return check_date.weekday() in (4, 5)
        return check_date.weekday() in (5, 6)

    def is_public_holiday(self, check_date: date) -> bool:
        """
        Uses the 'holidays' library to instantly check if the date 
        is an official public holiday in Malaysia.
        """
        return check_date in self.my_holidays

    def calculate_working_days(self, start_date: date, end_date: date) -> int:
        """
        Calculates the actual number of deductible leave days between two dates,
        completely skipping weekends and dynamic country public holidays.
        """
        if start_date > end_date:
            return 0

        working_days = 0
        current_date = start_date

        while current_date <= end_date:
            if not self.is_weekend(current_date) and not self.is_public_holiday(current_date):
                working_days += 1
            current_date += timedelta(days=1)

        return working_days
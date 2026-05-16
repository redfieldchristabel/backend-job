from typing import List
from typing import Optional
from sqlalchemy.orm import Session
from src.models import LeaveBalance
from datetime import date

class LeaveBalanceService:
    def __init__(self, db: Session):
        self.db = db

    def get_leave_balances(
        self,
        employee_id: int,
        year: Optional[int] = None,
    ) -> List[LeaveBalance]:
        """
        Get leave balances for an employee for a given year (defaults to current year).
        """
        if year is None:
            year = date.today().year

        balances = self.db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == year
        ).all()

        return balances
    
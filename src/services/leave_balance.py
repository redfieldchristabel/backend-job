from src.service import InsufficientBalanceError
from src.models import LeaveType
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

    def check_sufficient_balance(self, employee_id: int, leave_type: LeaveType, year: int, requested_days: int) -> LeaveBalance:
        balance = self.db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type == leave_type,
            LeaveBalance.year == year
        ).first()

        if not balance or (balance.remaining_days < requested_days):
            raise InsufficientBalanceError(employee_id, leave_type, balance.remaining_days if balance else 0, requested_days)
            
        return balance

    def revert_leave_days(self, employee_id: int, leave_type: LeaveType, year: int, days: float) -> LeaveBalance:
        """Rolls back deducted leave days when an approved request is cancelled."""
        balance = self.check_sufficient_balance(employee_id, leave_type, year, days)
        balance.used_days -= days
        return balance
"""
Business logic layer for leave management.

Implement the following service functions to handle leave request workflows.
Each function should raise appropriate exceptions for invalid operations
(e.g., overlapping leave, insufficient balance, self-approval).
"""

from typing import Any
from datetime import date

from sqlalchemy.orm import Session

from src.models import Employee, LeaveBalance, LeaveType


class LeaveError(Exception):
    status_code: int
    extra: dict[str, Any] = {}
    def __init__(self, message: str, status_code: int = 422, **kwargs: Any):
        self.status_code = status_code
        self.extra = kwargs
        super().__init__(message)

class LeaveNotFoundError(LeaveError):
    def __init__(self, leave_request_id: int):
        self.message = f"Leave request {leave_request_id} not found."
        super().__init__(self.message, 404, leave_request_id=leave_request_id)

class InsufficientBalanceError(LeaveError):
    def __init__(self, employee_id: int, leave_type: LeaveType, balance: float, requested: float):
        self.message = f"Employee {employee_id} has insufficient balance for leave type {leave_type}. Current balance: {balance}, Requested: {requested}"
        super().__init__(self.message, 409, balance=balance, requested=requested, employee_id=employee_id, leave_type=leave_type)


class OverlappingLeaveError(LeaveError):
    def __init__(self, employee_id: int):
        self.message = f"Employee {employee_id} has overlapping leave requests."
        super().__init__(self.message, 409)


class UnauthorizedApprovalError(LeaveError):
    def __init__(self, employee_id: int):
        self.message = f"Employee {employee_id} is not authorized to approve this leave request."
        super().__init__(
            message=self.message, 
            status_code=403
        )

def seed_demo_data(db: Session) -> None:
    """Seed database with demo employees and leave balances for testing."""
    from src.models import LeaveType, LeaveBalance

    existing = db.query(Employee).first()
    if existing:
        return

    alice = Employee(name="Alice Manager", email="alice@company.com", department="Engineering")
    bob = Employee(name="Bob Engineer", email="bob@company.com", department="Engineering", manager=alice)
    carol = Employee(name="Carol Engineer", email="carol@company.com", department="Engineering", manager=alice)
    db.add_all([alice, bob, carol])
    db.flush()

    year = date.today().year
    balances = [
        LeaveBalance(employee_id=bob.id, leave_type=LeaveType.ANNUAL, year=year, total_days=14),
        LeaveBalance(employee_id=bob.id, leave_type=LeaveType.SICK, year=year, total_days=12),
        LeaveBalance(employee_id=carol.id, leave_type=LeaveType.ANNUAL, year=year, total_days=14),
        LeaveBalance(employee_id=carol.id, leave_type=LeaveType.SICK, year=year, total_days=12),
    ]
    db.add_all(balances)
    db.commit()

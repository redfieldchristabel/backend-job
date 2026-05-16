from src.service import UnauthorizedApprovalError
from src.service import LeaveNotFoundError
from typing import Tuple
from typing import List
from src.service import InsufficientBalanceError
from src.models import LeaveBalance
from src.service import OverlappingLeaveError
from operator import and_
from src.models import LeaveStatus
from src.models import Employee
from src.service import LeaveError
from src.models import LeaveRequest
from typing import Optional
from src.models import LeaveType
from sqlalchemy.orm import Session
from datetime import date, datetime


class LeaveService:
    def __init__(self, db: Session):
        self.db = db

    def get_leave_requests(
        self,
        employee_id: Optional[int] = None,
        status: Optional[LeaveStatus] = None,
        leave_type: Optional[LeaveType] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[LeaveRequest], int]:
        """
        Retrieve leave requests with comprehensive filtering and pagination.
        Returns a tuple of (items, total_count).
        """
        # 1. Start the base query
        query = self.db.query(LeaveRequest)

        # 2. Apply Filters
        if employee_id:
            query = query.filter(LeaveRequest.employee_id == employee_id)

        if status:
            query = query.filter(LeaveRequest.status == status)
            
        if leave_type:
            query = query.filter(LeaveRequest.leave_type == leave_type)

        # Filter by start_date range
        if from_date:
            query = query.filter(LeaveRequest.start_date >= from_date)
            
        if to_date:
            query = query.filter(LeaveRequest.start_date <= to_date)

        # 3. Get total count before pagination
        total_count = query.count()

        # 4. Apply Sorting (Newest requests first)
        query = query.order_by(LeaveRequest.created_at.desc())

        # 5. Apply Pagination (Offset and Limit)
        offset = (page - 1) * page_size
        items = query.offset(offset).limit(page_size).all()

        return items, total_count


    def check_sufficient_balance(self, employee_id: int, leave_type: LeaveType, year: int, requested_days: int) -> LeaveBalance:
        balance = self.db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type == leave_type,
            LeaveBalance.year == year
        ).first()

        if not balance or (balance.remaining_days < requested_days):
            raise InsufficientBalanceError(employee_id, leave_type, balance.remaining_days if balance else 0, requested_days)
            
        return balance

    def create_leave_request(
        self,
        employee_id: int,
        leave_type: LeaveType,
        start_date: date,
        end_date: date,
        reason: Optional[str] = None,
    ) -> LeaveRequest:

        print(start_date)
        print(end_date)
        if start_date < date.today():
            raise LeaveError("Cannot create leave requests for past dates.")
        if start_date > end_date:
            raise LeaveError("Start date must be before or equal to end date.")

        if start_date.year != end_date.year:
            raise LeaveError("Start date and end date must be in the same year.")

        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            raise LeaveError(f"Employee {employee_id} not found.")

        overlap = self.db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            and_(LeaveRequest.start_date <= end_date, LeaveRequest.end_date >= start_date)
        ).first()
        if overlap:
            raise OverlappingLeaveError(employee_id)

        requested_days = (end_date - start_date).days + 1

        self.check_sufficient_balance(employee_id, leave_type, start_date.year, requested_days)

        new_request = LeaveRequest(
            employee_id=employee_id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status=LeaveStatus.PENDING
        )
        self.db.add(new_request)
        self.db.commit()
        self.db.refresh(new_request)
        return new_request



    def approve_leave_request(
        self,
        id: int,
        approver_id: int,
    ) -> LeaveRequest:
        leave : LeaveRequest = self.db.query(LeaveRequest).filter(LeaveRequest.id == id).first()

        if not leave:
            raise LeaveNotFoundError(id)
        
        manager_id = leave.employee.manager_id

        if leave.status != LeaveStatus.PENDING:
            raise LeaveError("Request is no longer pending.", 403)

        if manager_id != approver_id:
            raise UnauthorizedApprovalError(leave.employee_id)

        requested_days = leave.total_days

        balance = self.check_sufficient_balance(
            employee_id=leave.employee_id, 
            leave_type=leave.leave_type, 
            year=leave.start_date.year, 
            requested_days=requested_days
        )

        leave.status = LeaveStatus.APPROVED
        leave.approved_by = approver_id
        leave.approved_at = datetime.utcnow()

        balance.used_days += requested_days

        self.db.commit()
        self.db.refresh(leave)
        return leave

    def reject_leave_request(self, id: int, approver_id: int) -> LeaveRequest:
        leave : LeaveRequest = self.db.query(LeaveRequest).filter(LeaveRequest.id == id).first()

        if not leave:
            raise LeaveNotFoundError(id)

        manager_id = leave.employee.manager_id

        if leave.status != LeaveStatus.PENDING:
            raise LeaveError("Request is no longer pending.", 403)

        if manager_id != approver_id:
            raise UnauthorizedApprovalError(leave.employee_id)

        leave.status = LeaveStatus.REJECTED
        leave.approved_by = approver_id
        leave.approved_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(leave)
        return leave

    def cancel_leave_request(self, id: int, employee_id: int) -> LeaveRequest:
        request = self.db.query(LeaveRequest).filter(
            LeaveRequest.id == id,
        ).first()

        if not request:
            raise LeaveNotFoundError(id)

        if request.status == LeaveStatus.CANCELLED:
            raise LeaveError("Leave request has already been cancelled.", 403)

        if request.status != LeaveStatus.PENDING:
            raise LeaveError("Only Pending request can be cancelled.", 403)        

        if request.employee_id != employee_id:
            raise LeaveError("You are not authorized to cancel this leave request.", 403)

        request.status = LeaveStatus.CANCELLED
        self.db.commit()
        self.db.refresh(request)
        return request


    def get_leave_balances(
        self,
        employee_id: int,
        year: Optional[int] = None,
    ) -> List[LeaveBalance]:

        if year is None:
            year = date.today().year

        balances = self.db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == year
        ).all()

        return balances
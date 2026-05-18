import unittest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import Employee, LeaveType, LeaveStatus, LeaveRequest
from src.service import (
    seed_demo_data,
    LeaveError,
    LeaveNotFoundError,
    InsufficientBalanceError,
    OverlappingLeaveError,
    UnauthorizedApprovalError
)
from src.services.leave_request import LeaveService
from src.services.leave_balance import LeaveBalanceService

class TestLeaveServices(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite database specifically for isolation during tests
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()
        seed_demo_data(self.db)
        
        # Load the seeded dummy data
        self.alice = self.db.query(Employee).filter(Employee.email == "alice@company.com").first()
        self.bob = self.db.query(Employee).filter(Employee.email == "bob@company.com").first()
        
        # Instantiate services
        self.leave_service = LeaveService(self.db)
        self.balance_service = LeaveBalanceService(self.db)

    def tearDown(self):
        self.db.close()
        # Clean up database tables between test sets
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def test_create_leave_request_success(self):
        """Test valid leave creation ensures a PENDING request is added."""
        start = date.today() + timedelta(days=2)
        end = date.today() + timedelta(days=4)
        
        req = self.leave_service.create_leave_request(
            employee_id=self.bob.id,
            leave_type=LeaveType.ANNUAL,
            start_date=start,
            end_date=end,
            reason="Vacation"
        )
        self.assertEqual(req.status, LeaveStatus.PENDING)
        self.assertEqual(req.total_days, 3)

    def test_create_leave_past_date_fails(self):
        """Test creating leave in the past throws a standard LeaveError."""
        past_date = date.today() - timedelta(days=5)
        with self.assertRaises(LeaveError):
            self.leave_service.create_leave_request(
                employee_id=self.bob.id,
                leave_type=LeaveType.ANNUAL,
                start_date=past_date,
                end_date=past_date
            )

    def test_create_leave_insufficient_balance(self):
        """Test requesting more leave days than remaining in balance throws InsufficientBalanceError."""
        start = date.today() + timedelta(days=1)
        end = date.today() + timedelta(days=30) # Bob only has 14 days
        
        with self.assertRaises(InsufficientBalanceError):
            self.leave_service.create_leave_request(
                employee_id=self.bob.id,
                leave_type=LeaveType.ANNUAL,
                start_date=start,
                end_date=end
            )

    def test_approve_leave_unauthorized_approver(self):
        """Test that non-managers (or self-approvers) throw an UnauthorizedApprovalError."""
        start = date.today() + timedelta(days=2)
        end = date.today() + timedelta(days=2)
        req = self.leave_service.create_leave_request(self.bob.id, LeaveType.ANNUAL, start, end)
        
        # Bob cannot approve his own leave request (Alice is his manager)
        with self.assertRaises(UnauthorizedApprovalError):
            self.leave_service.approve_leave_request(id=req.id, approver_id=self.bob.id)

    def test_get_leave_balances(self):
        """Verify the balance service queries correct data maps."""
        balances = self.balance_service.get_leave_balances(employee_id=self.bob.id)
        self.assertTrue(len(balances) > 0)
        self.assertEqual(balances[0].employee_id, self.bob.id)


    def test_cancel_pending_leave_request_success(self):
        """Verify that an employee can cancel their own PENDING request successfully."""
        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=6)
        
        # 1. Create a pending request
        req = self.leave_service.create_leave_request(
            employee_id=self.bob.id,
            leave_type=LeaveType.ANNUAL,
            start_date=start,
            end_date=end
        )
        
        # 2. Cancel the pending request
        cancelled_req = self.leave_service.cancel_leave_request(id=req.id, employee_id=self.bob.id)
        
        self.assertEqual(cancelled_req.status, LeaveStatus.CANCELLED)

    def test_cancel_leave_unauthorized_owner(self):
        """Verify that an employee CANNOT cancel another employee's leave request."""
        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=6)
        
        # Bob creates a request
        req = self.leave_service.create_leave_request(self.bob.id, LeaveType.ANNUAL, start, end)
        
        # Alice tries to cancel Bob's request (should raise LeaveError 403)
        with self.assertRaises(LeaveError) as context:
            self.leave_service.cancel_leave_request(id=req.id, employee_id=self.alice.id)
            
        self.assertEqual(context.exception.status_code, 403)

    def test_cancel_approved_leave_restores_balance(self):
        """Verify that cancelling an APPROVED leave request reverts used_days accurately."""
        from src.models import LeaveBalance
        
        # 1. Find Bob's initial balance state
        balance = self.db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == self.bob.id,
            LeaveBalance.leave_type == LeaveType.ANNUAL
        ).first()
        initial_used_days = balance.used_days

        # 2. Create a leave request
        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=7)
        req = self.leave_service.create_leave_request(self.bob.id, LeaveType.ANNUAL, start, end)
        
        # 3. Approve the request (which increments used_days balance)
        self.leave_service.approve_leave_request(id=req.id, approver_id=self.alice.id)
        self.db.commit()
        self.assertEqual(balance.used_days, initial_used_days + req.total_work_days)

        # 4. Bob cancels the approved request
        self.leave_service.cancel_leave_request(id=req.id, employee_id=self.bob.id)
        self.db.commit()

        # 5. CRUCIAL ASSERTION: used_days must return back to its original state
        self.assertEqual(balance.used_days, initial_used_days)
        self.assertEqual(req.status, LeaveStatus.CANCELLED)

    def test_cancel_already_cancelled_leave_fails(self):
        """Verify that attempting to cancel a request that is already CANCELLED throws an error."""
        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=6)
        req = self.leave_service.create_leave_request(self.bob.id, LeaveType.ANNUAL, start, end)
        
        # First cancellation
        self.leave_service.cancel_leave_request(id=req.id, employee_id=self.bob.id)
        
        # Second cancellation attempt should fail with 403
        with self.assertRaises(LeaveError) as context:
            self.leave_service.cancel_leave_request(id=req.id, employee_id=self.bob.id)
            
        self.assertEqual(context.exception.status_code, 403)


    def test_leave_skips_real_malaysian_holidays(self):
        """Verify that the CalendarService correctly calculates working days, skipping public holidays and weekends."""
        from src.services.calendar import CalendarService
        calendar_service = CalendarService()
        
        # May 1st 2026 (Labour Day) is a Friday (Public Holiday)
        # May 2nd is Saturday (Weekend)
        # May 3rd is Sunday (Weekend)
        # May 4th is Monday (Working day)
        start = date(2026, 5, 1)
        end = date(2026, 5, 4)
        
        working_days = calendar_service.calculate_working_days(start, end)
        
        # Total span is 4 days, but it should only count 1 working day (May 4th)!
        self.assertEqual(working_days, 1)
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
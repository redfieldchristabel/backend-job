"""
Tests for the leave management service layer.

These tests are currently empty and use placeholder asserts.
When you implement src/services.py, write real tests here.

Consider:
- What happens when you try to create overlapping leave?
- What happens when balance is insufficient?
- Can an employee approve their own leave?
- Can you cancel an already-cancelled leave?
- Does cancelling an approved leave restore the balance?
"""

import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import LeaveType, LeaveStatus
from src.service import (
    seed_demo_data,
    create_leave_request,
    approve_leave_request,
    cancel_leave_request,
    get_leave_requests,
    get_leave_balances,
    InsufficientBalanceError,
    OverlappingLeaveError,
    SelfApprovalError,
)


class TestLeaveServices(unittest.TestCase):
    """You must implement and expand these tests."""

    @classmethod
    def setUpClass(cls):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        cls.Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def setUp(self):
        self.db = self.Session()
        seed_demo_data(self.db)
        # Fetch demo employees
        from src.models import Employee
        self.alice = self.db.query(Employee).filter(Employee.email == "alice@company.com").first()
        self.bob = self.db.query(Employee).filter(Employee.email == "bob@company.com").first()
        self.carol = self.db.query(Employee).filter(Employee.email == "carol@company.com").first()

    def tearDown(self):
        self.db.close()

    def test_create_leave_request(self):
        # TODO: implement
        self.assertTrue(True)

    def test_create_leave_request_insufficient_balance(self):
        # TODO: implement
        self.assertTrue(True)

    def test_create_leave_request_overlapping_dates(self):
        # TODO: implement
        self.assertTrue(True)

    def test_approve_leave_request(self):
        # TODO: implement
        self.assertTrue(True)

    def test_self_approval_rejected(self):
        # TODO: implement
        self.assertTrue(True)

    def test_cancel_approved_leave_restores_balance(self):
        # TODO: implement
        self.assertTrue(True)

    def test_list_leave_requests_with_filters(self):
        # TODO: implement
        self.assertTrue(True)

    def test_get_leave_balances(self):
        # TODO: implement
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()

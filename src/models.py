from src.services.calendar import CalendarService
from sqlalchemy.orm import Mapped
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Enum as SqlEnum
from sqlalchemy.orm import relationship
import enum

from src.database import Base


class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LeaveType(str, enum.Enum):
    ANNUAL = "annual"
    SICK = "sick"
    PERSONAL = "personal"
    MATERNITY = "maternity"
    PATERNITY = "paternity"
    UNPAID = "unpaid"


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    department = Column(String, nullable=False)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    joined_at = Column(Date, default=date.today)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = relationship("Employee", remote_side="Employee.id")
    leave_requests = relationship(
        "LeaveRequest", 
        back_populates="employee", 
        foreign_keys="[LeaveRequest.employee_id]"
    )
    leave_balances = relationship("LeaveBalance", back_populates="employee")


class LeaveRequest(Base):
    
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    leave_type = Column(SqlEnum(LeaveType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String, nullable=True)
    status = Column(SqlEnum(LeaveStatus), default=LeaveStatus.PENDING)
    approved_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee : Mapped["Employee"] = relationship(
        "Employee", 
        back_populates="leave_requests", 
        foreign_keys=[employee_id]
    )
    approver : Mapped["Employee"] = relationship("Employee", foreign_keys=[approved_by])

    @property
    def total_days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def total_work_days(self) -> int:
        return CalendarService().calculate_working_days(self.start_date, self.end_date)

    @property
    def response(self):
        from src.app import LeaveRequestOut

        return LeaveRequestOut(
            id=self.id,
            employee_id=self.employee_id,
            leave_type=self.leave_type,
            start_date=self.start_date,
            end_date=self.end_date,
            reason=self.reason,
            status=self.status,
            days=self.total_work_days,
            approved_by=self.approver.name if self.approver else None,
            approved_at=self.approved_at.strftime("%d/%m/%Y %H:%M:%S") if self.approved_at else None
        )

class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    leave_type = Column(SqlEnum(LeaveType), nullable=False)
    year = Column(Integer, nullable=False)
    total_days = Column(Float, nullable=False, default=0)
    used_days = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("Employee", back_populates="leave_balances")

    @property
    def remaining_days(self) -> float:
        return self.total_days - self.used_days

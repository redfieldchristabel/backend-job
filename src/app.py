"""
FastAPI application for Kakitangan Leave Management System.

This is the entrypoint. Routes are defined but most business logic
in services.py needs to be implemented to make everything work.
"""

from anyio import sleep
from functools import wraps
from src.services.lock import LockService
from src.current_user import get_current_user
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.service import LeaveError
from src.services.leave_request import LeaveService
from src.services.leave_balance import LeaveBalanceService
from datetime import date
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import engine, get_db, Base
from src.models import LeaveType, LeaveStatus
from src import service

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Kakitangan Leave Management API", version="0.1.0")

lock_service = LockService()

# ── Decorators ───────────────────────────────────────────────────────────────

def lock_request(expire_seconds: int = 5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Python inspects the route parameters automatically!
            request: Request = kwargs.get("request")
            
            # 2. If it finds them, it handles the generation and safety injection rules
            if request:
                lock_key = f"{request.method}:{request.url.path}" # HTTP method plus full path
                lock_service.acquire_and_track(request, lock_key, expire_seconds)
                
            return func(*args, **kwargs)
        return wrapper
    return decorator

# ── Schemas ──────────────────────────────────────────────────────────────

class EmployeeOut(BaseModel):
    id: int
    name: str
    email: str
    department: str
    manager_id: Optional[int] = None

    class Config:
        from_attributes = True


class LeaveBalanceOut(BaseModel):
    id: int
    leave_type: LeaveType
    year: int
    total_days: float
    used_days: float
    remaining_days: float

    class Config:
        from_attributes = True


class LeaveRequestCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None

class LeaveRequestStatusUpdate(BaseModel):
    status: LeaveStatus

class LeaveRequestOut(BaseModel):
    id: int
    employee_id: int
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str]
    status: LeaveStatus
    days: Optional[float] = None
    approved_by: Optional[str]
    approved_at: Optional[str]

    class Config:
        from_attributes = True

class PaginatedLeaveRequests(BaseModel):
    items: list[LeaveRequestOut]
    total: int
    page: int
    page_size: int


# ── Routes ───────────────────────────────────────────────────────────────

@app.get("/employees", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    from src.models import Employee
    return db.query(Employee).all()


@app.get("/employees/{employee_id}", response_model=dict)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    from src.models import Employee

    service = LeaveService(db)

    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    balances = service.get_leave_balances(employee_id)
    return {
        "employee": EmployeeOut.model_validate(emp),
        "leave_balances": [LeaveBalanceOut.model_validate(b) for b in balances],
    }

@app.get("/employees/{employee_id}/leave-balances", response_model=list[LeaveBalanceOut])
def get_balance(employee_id: int, year: Optional[int] = Query(None), db: Session = Depends(get_db)):

    service = LeaveBalanceService(db)
    print(employee_id)

    balances = service.get_leave_balances(employee_id=employee_id, year=year)
    return [LeaveBalanceOut.model_validate(b) for b in balances]


@app.get("/leave-requests", response_model=PaginatedLeaveRequests)
def list_leave_requests(
    employee_id: Optional[int] = Query(None),
    status: Optional[LeaveStatus] = Query(None),
    leave_type: Optional[LeaveType] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = LeaveService(db)
    items, total = service.get_leave_requests(
        employee_id=employee_id, status=status, leave_type=leave_type,
        from_date=from_date, to_date=to_date, page=page, page_size=page_size,
    )
    return PaginatedLeaveRequests(
        items=[LeaveRequestOut.model_validate(i.response) for i in items],
        total=total, page=page, page_size=page_size,
    )

@app.post("/leave-requests", response_model=LeaveRequestOut, status_code=201)
def create_leave_request(
    body: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    ):
    service = LeaveService(db)

    return service.create_leave_request(employee_id=current_user.id,
     end_date=body.end_date, leave_type=body.leave_type,
      reason=body.reason, start_date=body.start_date).response

@app.get("/leave-requests/{leave_request_id}", response_model=LeaveRequestOut)
def get_leave_request(leave_request_id: int, db: Session = Depends(get_db)):
    from src.models import LeaveRequest
    lr = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if not lr:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return lr.response


@app.put("/leave-requests/{leave_request_id}/status", response_model=LeaveRequestOut)
@lock_request()
async def update_leave_request_status(
        request: Request,
        leave_request_id: int, body: LeaveRequestStatusUpdate,
        db: Session = Depends(get_db),
        current_user = Depends(get_current_user)
    ):
    service = LeaveService(db)

    lr = None

    match body.status:
        case LeaveStatus.CANCELLED:
            lr = service.cancel_leave_request(id=leave_request_id, employee_id=current_user.id)
        case LeaveStatus.APPROVED:
            lr = service.approve_leave_request(id=leave_request_id, approver_id=current_user.id)
        case LeaveStatus.REJECTED:
            lr = service.reject_leave_request(id=leave_request_id, approver_id=current_user.id)
        case _:
            raise LeaveError("Status not supported yet", 400)
    

    return lr.response



@app.exception_handler(LeaveError)
async def leave_error_handler(request: Request, exc: LeaveError):
    extra = exc.extra if exc.extra else None
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "type": exc.__class__.__name__,
            "message": str(exc),
            "extra_info": extra
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # This transforms the Pydantic error into a custom format
    errors = []
    for error in exc.errors():
        errors.append({
            "field": error["loc"][-1], # Gets the field name
            "message": error["msg"],
            "type": error["type"]
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation failed",
            "errors": errors
        },
    )

@app.middleware("http")
async def release_lock_middleware(request: Request, call_next):
    print("iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii")
    response = await call_next(request)
    if hasattr(request.state, "acquired_locks"):
        for lock_key in request.state.acquired_locks:
            lock_service.release_lock(lock_key)
            
    return response


@app.on_event("startup")
def on_startup():
    db = next(get_db())
    try:
        service.seed_demo_data(db)
    finally:
        db.close()

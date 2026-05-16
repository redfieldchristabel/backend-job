from fastapi import HTTPException
from src.models import Employee
from src.database import get_db
from fastapi import Depends
from sqlalchemy.orm import Session
from fastapi import Header
from typing import Optional

def get_current_user(
    x_current_user: Optional[int] = Header(None, alias="X-Current-User"),
    db: Session = Depends(get_db)
) -> Employee:
    if x_current_user is None:
        raise HTTPException(status_code=401, detail="add X-Current-User header for mimicking the authentication")
    
    user = db.query(Employee).filter(Employee.id == x_current_user).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user
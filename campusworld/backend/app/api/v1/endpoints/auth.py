"""
Authentication endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from app.schemas.auth import Token, UserCreate
from app.ssh.game_handler import game_handler

router = APIRouter()


@router.post("/register", response_model=Token)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user (SQL legacy table; graph account required for CLI/WS)."""
    # Check if user already exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(subject=user.email)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login with the same graph account credentials as SSH (`Node.name` / account name).
    OAuth2 `username` field carries the campus account name, not necessarily an email.
    """
    client_ip = request.client.host if request.client else "unknown"
    result = game_handler.authenticate_user(
        username=form_data.username,
        password=form_data.password,
        client_ip=client_ip,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = result["user_id"]
    username = result["username"]
    access_token = create_access_token(subject=str(user_id), username=username)
    return {"access_token": access_token, "token_type": "bearer"}

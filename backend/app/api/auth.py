from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas.common import UserCreate, UserOut, Token
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_current_user
from app.services.audit import audit
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email.lower())): raise HTTPException(409, "Email already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), full_name=payload.full_name)
    db.add(user); db.commit(); db.refresh(user); audit(db, "USER_REGISTERED", user); db.commit(); return user

@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not verify_password(form.password, user.password_hash):
        audit(db, "AUTH_FAILED", metadata={"email": form.username.lower()}); db.commit(); raise HTTPException(401, "Invalid credentials")
    audit(db, "AUTH_SUCCESS", user); db.commit(); return Token(access_token=create_access_token(str(user.id)))

@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)): return user

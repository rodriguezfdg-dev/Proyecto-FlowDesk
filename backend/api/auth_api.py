# backend/api/auth_api.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from werkzeug.security import check_password_hash, generate_password_hash # Added generate_password_hash
from datetime import datetime, timedelta
import hashlib
from pydantic import BaseModel # Added BaseModel
import random # Added random
import string # Added string

from backend.database import get_db
from backend.models import PersonOfCustomer
from backend.core.email import send_email # Added send_email

# --- Configuration ---
import os
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv('.env.local')

SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_in_a_config_file")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# --- Security ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")

router = APIRouter(
    prefix="/api",
    tags=["Authentication"]
)

# --- Helper Functions ---
def verify_password_legacy(plain_password, hashed_password):
    """Verifies a SHA256 hashed password."""
    return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == hashed_password

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Pydantic Models for Registration
class RegisterRequest(BaseModel):
    user: str
    gmail: str
    password: str

@router.post("/register", status_code=status.HTTP_201_CREATED, tags=["Authentication"])
async def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if user or gmail already exists
    existing_user = db.query(PersonOfCustomer).filter(
        or_(
            PersonOfCustomer.user == request.user,
            PersonOfCustomer.gmail == request.gmail
        )
    ).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or email already registered")

    # Hash password
    hashed_password = generate_password_hash(request.password)
    
    # Generate verification code
    verification_code = ''.join(random.choices(string.digits, k=6)) # 6-digit code

    # Create new user
    new_user = PersonOfCustomer(
        user=request.user,
        gmail=request.gmail,
        hashed_password=hashed_password,
        verification_code=verification_code,
        is_verified=False,
        roll='2', # Default roll for new users (e.g., regular customer)
        status=0 # Default status
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Send verification email
    email_sent = send_email(
        to_email=new_user.gmail,
        subject="Verificación de Cuenta",
        body=f"Hola {new_user.user},<br><br>Gracias por registrarte. Tu código de verificación es: <b>{verification_code}</b><br><br>Por favor, usa este código para verificar tu cuenta."
    )

    if not email_sent:
        # If email sending fails, rollback the user creation
        db.delete(new_user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please check SMTP settings."
        )

    return {"message": "User registered successfully. Please check your email for verification code."}

class VerifyRequest(BaseModel):
    user: str
    code: str

@router.post("/verify", status_code=status.HTTP_200_OK, tags=["Authentication"])
async def verify_user(request: VerifyRequest, db: Session = Depends(get_db)):
    db_person = db.query(PersonOfCustomer).filter(PersonOfCustomer.user == request.user).first()
    if not db_person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if db_person.verification_code != request.code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    db_person.is_verified = True
    db_person.verification_code = None
    db.commit()

    return {"message": "Account verified successfully"}

class ForgotPasswordRequest(BaseModel):
    email: str

@router.post("/forgot-password", status_code=status.HTTP_200_OK, tags=["Authentication"])
async def forgot_password(request: ForgotPasswordRequest, req: Request, db: Session = Depends(get_db)):
    print(f"DEBUG: forgot_password called with email: {request.email}")
    
    db_person = db.query(PersonOfCustomer).filter(PersonOfCustomer.gmail == request.email).first()
    
    print(f"DEBUG: User found in database: {db_person is not None}")
    
    if not db_person:
        # To prevent user enumeration, we don't reveal that the user doesn't exist.
        # We just return a success message as if the email was sent.
        print("DEBUG: User not found, returning generic success message")
        return {"message": "If an account with this email exists, a password reset link has been sent."}

    # Generate and store reset token
    reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    db_person.reset_token = reset_token
    db_person.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    # Send password reset email
    # Use the origin from the request headers, or fallback to localhost
    origin = req.headers.get("origin")
    print(f"DEBUG: Origin header: {origin}")
    
    if not origin:
        # Fallback logic: try to construct from host header if origin is missing
        host = req.headers.get("host")
        print(f"DEBUG: Host header: {host}")
        if host:
            origin = f"http://{host}"
        else:
            origin = "http://127.0.0.1:5000"
    
    print(f"DEBUG: Final origin for reset link: {origin}")
    reset_link = f"{origin}/reset_password?token={reset_token}"
    print(f"DEBUG: Reset link: {reset_link}")
    
    email_sent = send_email(
        to_email=db_person.gmail,
        subject="Reseteo de Contraseña",
        body=f"Hola {db_person.user},<br><br>Recibimos una solicitud para resetear tu contraseña. Haz clic en el siguiente enlace para continuar:<br><br>"
             f"<a href='{reset_link}'>{reset_link}</a><br><br>"
             f"Si no solicitaste esto, puedes ignorar este correo. El enlace expirará en 1 hora."
    )
    
    print(f"DEBUG: Email sent result: {email_sent}")

    if not email_sent:
        # Don't rollback the token, but raise an error so the user knows something went wrong.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send password reset email. Please try again later."
        )

    return {"message": "If an account with this email exists, a password reset link has been sent."}

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/reset-password", status_code=status.HTTP_200_OK, tags=["Authentication"])
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    db_person = db.query(PersonOfCustomer).filter(PersonOfCustomer.reset_token == request.token).first()
    
    if not db_person or db_person.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    # Update password and clear token
    db_person.hashed_password = generate_password_hash(request.new_password)
    db_person.reset_token = None
    db_person.reset_token_expires = None
    db.commit()

    return {"message": "Password has been reset successfully."}


# --- API Endpoints ---
from sqlalchemy import or_

# ... (omitting unchanged code for brevity) ...

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(PersonOfCustomer).filter(
        or_(
            PersonOfCustomer.user == form_data.username,
            PersonOfCustomer.gmail == form_data.username
        )
    ).first()
    
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Try modern hash check first, fallback to legacy SHA256
    password_verified = False
    try:
        # Werkzeug's check_password_hash works for hashes like 'bcrypt_sha256' etc.
        if check_password_hash(user.hashed_password, form_data.password):
            password_verified = True
    except Exception:
        # This will likely fail if the hash is a plain SHA256 string.
        pass

    if not password_verified:
        if verify_password_legacy(form_data.password, user.hashed_password):
            password_verified = True
            # TODO: Add a logging mechanism to flag this user for password migration.
            # print(f"User {user.user} logged in with legacy password. Migration needed.")
    
    if not password_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.user, "id": user.id, "roll": user.roll}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": {
            "username": user.user,
            "roll": user.roll
        }
    }


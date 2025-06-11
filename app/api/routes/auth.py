from datetime import datetime, timedelta
from typing import Optional
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, validator, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db
from app.db import crud, models
from app.config import settings
from app.utils.logger import logger

# Setup router
router = APIRouter()

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Models
class Token(BaseModel):
   access_token: str
   token_type: str
   user_id: str
   full_name: Optional[str] = None

class TokenData(BaseModel):
   email: Optional[str] = None
   user_id: Optional[str] = None

class UserCreate(BaseModel):
   email: EmailStr
   password: str
   full_name: Optional[str] = None
   slack_user_id: Optional[str] = None
   whatsapp_number: Optional[str] = None
   
   @validator('password')
   def validate_password(cls, v):
       if len(v) < 8:
           raise ValueError('Password must be at least 8 characters long')
       if not re.search(r'[A-Z]', v):
           raise ValueError('Password must contain at least one uppercase letter')
       if not re.search(r'[a-z]', v):
           raise ValueError('Password must contain at least one lowercase letter')
       if not re.search(r'[0-9]', v):
           raise ValueError('Password must contain at least one digit')
       return v
   
   @validator('slack_user_id')
   def validate_slack_id(cls, v):
       if v and not re.match(r'^[UW][A-Z0-9]{8,}$', v):
           raise ValueError('Invalid Slack User ID format. It should start with U or W followed by alphanumeric characters')
       return v
   
   @validator('whatsapp_number')
   def validate_whatsapp(cls, v):
       if v:
           # Remove spaces and dashes
           cleaned = re.sub(r'[\s\-]', '', v)
           # Check if it starts with + and contains only digits after that
           if not re.match(r'^\+\d{10,15}$', cleaned):
               raise ValueError('Invalid WhatsApp number. Must start with + followed by country code and number (10-15 digits total)')
           return cleaned
       return v

class UserResponse(BaseModel):
   id: str
   email: str
   full_name: Optional[str] = None
   is_active: bool
   is_superuser: bool
   slack_user_id: Optional[str] = None
   whatsapp_number: Optional[str] = None
   
   class Config:
       orm_mode = True

# Helper functions
def verify_password(plain_password, hashed_password):
   return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
   return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
   to_encode = data.copy()
   if expires_delta:
       expire = datetime.utcnow() + expires_delta
   else:
       expire = datetime.utcnow() + timedelta(days=7)  # Default to 7 days
   to_encode.update({"exp": expire})
   encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
   return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_async_db)):
   credentials_exception = HTTPException(
       status_code=status.HTTP_401_UNAUTHORIZED,
       detail="Could not validate credentials",
       headers={"WWW-Authenticate": "Bearer"},
   )
   try:
       payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
       email: str = payload.get("sub")
       user_id: str = payload.get("user_id")
       if email is None and user_id is None:
           raise credentials_exception
       token_data = TokenData(email=email, user_id=user_id)
   except JWTError:
       raise credentials_exception
   
   if token_data.user_id:
       # Use the user_id as a string without converting to int
       user = await crud.get_user(db, token_data.user_id)
   else:
       user = await crud.get_user_by_email(db, token_data.email)
       
   if user is None:
       raise credentials_exception
   if not user.is_active:
       raise HTTPException(status_code=400, detail="Inactive user")
   return user

async def get_current_active_user(current_user = Depends(get_current_user)):
   if not current_user.is_active:
       raise HTTPException(status_code=400, detail="Inactive user")
   return current_user

# Routes

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_async_db)):
   user = await crud.get_user_by_email(db, form_data.username)
   if not user or not verify_password(form_data.password, user.hashed_password):
       raise HTTPException(
           status_code=status.HTTP_401_UNAUTHORIZED,
           detail="Incorrect email or password",
           headers={"WWW-Authenticate": "Bearer"},
       )
   access_token_expires = timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
   access_token = create_access_token(
       data={"sub": user.email, "user_id": str(user.id)}, expires_delta=access_token_expires
   )
   return {
       "access_token": access_token, 
       "token_type": "bearer",
       "user_id": str(user.id),
       "full_name": user.full_name
   }

@router.post("/register", response_model=Token)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_async_db)):
   # Check if user already exists
   existing_user = await crud.get_user_by_email(db, user_data.email)
   if existing_user:
       raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail="Email already registered"
       )
   
   # Check if Slack ID is already in use
   if user_data.slack_user_id:
       existing_slack_user = await crud.get_user_by_slack_id(db, user_data.slack_user_id)
       if existing_slack_user:
           raise HTTPException(
               status_code=status.HTTP_400_BAD_REQUEST,
               detail="This Slack User ID is already registered with another account"
           )
   
   # Check if WhatsApp number is already in use
   if user_data.whatsapp_number:
       existing_whatsapp_user = await crud.get_user_by_whatsapp(db, user_data.whatsapp_number)
       if existing_whatsapp_user:
           raise HTTPException(
               status_code=status.HTTP_400_BAD_REQUEST,
               detail="This WhatsApp number is already registered with another account"
           )
   
   # Hash the password
   hashed_password = get_password_hash(user_data.password)
   
   # Create user in database
   new_user = await crud.create_user(db, {
       "email": user_data.email,
       "hashed_password": hashed_password,
       "full_name": user_data.full_name,
       "slack_user_id": user_data.slack_user_id,
       "whatsapp_number": user_data.whatsapp_number,
       "is_active": True,
       "is_superuser": False
   })
   
   logger.info(f"New user registered: {new_user.email}, Slack: {new_user.slack_user_id}, WhatsApp: {new_user.whatsapp_number}")
   
   # Create access token
   access_token_expires = timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
   access_token = create_access_token(
       data={"sub": new_user.email, "user_id": str(new_user.id)}, expires_delta=access_token_expires
   )
   
   return {
       "access_token": access_token, 
       "token_type": "bearer",
       "user_id": str(new_user.id),
       "full_name": new_user.full_name
   }

@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user = Depends(get_current_active_user)):
    # Convert the UUID to a string before returning
    user_dict = {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "slack_user_id": current_user.slack_user_id,
        "whatsapp_number": current_user.whatsapp_number,
    }
    return user_dict

@router.put("/users/me", response_model=UserResponse)
async def update_user_profile(
    user_data: dict,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update user profile information"""
    # Validate Slack ID if provided
    if 'slack_user_id' in user_data and user_data['slack_user_id']:
        if not re.match(r'^[UW][A-Z0-9]{8,}$', user_data['slack_user_id']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Slack User ID format"
            )
        # Check if already in use by another user
        existing = await crud.get_user_by_slack_id(db, user_data['slack_user_id'])
        if existing and existing.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This Slack User ID is already in use"
            )
    
    # Validate WhatsApp number if provided
    if 'whatsapp_number' in user_data and user_data['whatsapp_number']:
        cleaned = re.sub(r'[\s\-]', '', user_data['whatsapp_number'])
        if not re.match(r'^\+\d{10,15}$', cleaned):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid WhatsApp number format"
            )
        user_data['whatsapp_number'] = cleaned
        # Check if already in use by another user
        existing = await crud.get_user_by_whatsapp(db, cleaned)
        if existing and existing.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This WhatsApp number is already in use"
            )
    
    # Update user
    updated_user = await crud.update_user(db, str(current_user.id), user_data)
    
    return {
        "id": str(updated_user.id),
        "email": updated_user.email,
        "full_name": updated_user.full_name,
        "is_active": updated_user.is_active,
        "is_superuser": updated_user.is_superuser,
        "slack_user_id": updated_user.slack_user_id,
        "whatsapp_number": updated_user.whatsapp_number,
    }
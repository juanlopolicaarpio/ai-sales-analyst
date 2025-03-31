from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
import time

from app.config import settings
from app.db.database import get_async_db
from app.db import crud
from app.utils.logger import logger

security = HTTPBearer()

class RBACMiddleware:
    """Role-based access control middleware."""
    
    @staticmethod
    async def verify_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_async_db)
    ) -> Dict[str, Any]:
        """
        Verify JWT token and return payload.
        """
        try:
            # Get token from authorization header
            token = credentials.credentials
            
            # Decode token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            
            # Check if token is expired
            if payload.get("exp") and time.time() > payload.get("exp"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Get user from database
            user_id = payload.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            user = await crud.get_user(db, user_id)
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Add user to payload
            payload["user"] = {
                "id": str(user.id),
                "email": user.email,
                "is_superuser": user.is_superuser
            }
            
            return payload
            
        except JWTError as e:
            logger.error(f"JWT error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication error",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    @staticmethod
    async def verify_store_access(
        store_id: str,
        token_payload: Dict[str, Any] = Depends(verify_token),
        db: AsyncSession = Depends(get_async_db)
    ) -> Dict[str, Any]:
        """
        Verify user has access to store.
        """
        try:
            user_id = token_payload["user"]["id"]
            
            # Get stores for user
            user_stores = await crud.get_stores_by_user(db, user_id)
            
            # Check if user has access to store
            store = next((s for s in user_stores if str(s.id) == store_id), None)
            if not store:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this store"
                )
            
            # Add store to payload
            token_payload["store"] = {
                "id": str(store.id),
                "name": store.name,
                "platform": store.platform
            }
            
            return token_payload
        except Exception as e:
            logger.error(f"Store access verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access verification error"
            )
    
    @staticmethod
    async def verify_admin(
        token_payload: Dict[str, Any] = Depends(verify_token)
    ) -> Dict[str, Any]:
        """
        Verify user is an admin.
        """
        if not token_payload["user"].get("is_superuser"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        return token_payload


# Dependency to protect routes requiring authentication
async def get_current_user(
    token_payload: Dict[str, Any] = Depends(RBACMiddleware.verify_token),
    db: AsyncSession = Depends(get_async_db)
):
    """Get current user based on token."""
    return await crud.get_user(db, token_payload["user"]["id"])


# Dependency to protect routes requiring store access
async def get_store_access(
    store_id: str,
    token_payload: Dict[str, Any] = Depends(RBACMiddleware.verify_token),
    db: AsyncSession = Depends(get_async_db)
):
    """Get store if user has access."""
    await RBACMiddleware.verify_store_access(store_id, token_payload, db)
    return await crud.get_store(db, store_id)


# Dependency to protect admin routes
async def get_admin_access(
    token_payload: Dict[str, Any] = Depends(RBACMiddleware.verify_token)
):
    """Verify admin access."""
    await RBACMiddleware.verify_admin(token_payload)
    return token_payload
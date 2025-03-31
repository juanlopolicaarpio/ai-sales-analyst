import json
import secrets
import hmac
import hashlib
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.config import settings
from app.db.database import get_async_db
from app.db import crud, models
from app.api.routes.auth import create_access_token
from app.api.middleware.security import get_current_user
from app.utils.logger import logger

router = APIRouter()

# Store nonce values temporarily (In production, use Redis or similar)
NONCE_STORE = {}

@router.get("/shopify/auth")
async def start_shopify_auth(
    shop: str,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Start Shopify OAuth flow.
    """
    if not shop.endswith('myshopify.com') and not shop.endswith('shopify.com'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid shop domain. Must be a myshopify.com domain."
        )

    nonce = secrets.token_hex(16)
    NONCE_STORE[nonce] = {
        "user_id": str(current_user.id),
        "shop": shop,
        "timestamp": datetime.utcnow().isoformat()
    }

    scopes = [
        "read_products",
        "read_orders",
        "read_customers",
        "read_inventory"
    ]

    params = {
        "client_id": settings.SHOPIFY_API_KEY,
        "scope": ",".join(scopes),
        "redirect_uri": f"{settings.APP_URL}/api/shopify/callback",
        "state": nonce
    }

    auth_url = f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(auth_url)

@router.get("/shopify/callback")
async def shopify_callback(
    request: Request,
    shop: Optional[str] = None,
    code: Optional[str] = None,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Handle Shopify OAuth callback.
    """
    if not shop or not code or not state:
        logger.error(f"Missing required parameters: shop={shop}, code={bool(code)}, state={bool(state)}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=invalid_request")

    nonce_data = NONCE_STORE.pop(state, None)
    if not nonce_data:
        logger.error(f"Invalid state parameter: {state}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=invalid_state")

    if nonce_data["shop"] != shop:
        logger.error(f"Shop mismatch: {nonce_data['shop']} != {shop}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=shop_mismatch")

    nonce_timestamp = datetime.fromisoformat(nonce_data["timestamp"])
    if datetime.utcnow() - nonce_timestamp > timedelta(minutes=10):
        logger.error(f"Nonce expired: {nonce_timestamp}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=expired_request")

    if not validate_hmac(request):
        logger.error("HMAC validation failed")
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=validation_failed")

    try:
        token_url = f"https://{shop}/admin/oauth/access_token"
        payload = {
            "client_id": settings.SHOPIFY_API_KEY,
            "client_secret": settings.SHOPIFY_API_SECRET,
            "code": code
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, json=payload)
            response.raise_for_status()
            token_data = response.json()

            access_token = token_data.get("access_token")
            if not access_token:
                logger.error(f"No access token in response: {token_data}")
                return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=no_access_token")

            user_id = nonce_data["user_id"]
            shop_info = await get_shop_info(shop, access_token)

            existing_store = None
            user_stores = await crud.get_stores_by_user(db, user_id)
            for store in user_stores:
                if store.store_url == shop:
                    existing_store = store
                    break

            if existing_store:
                await crud.update_store(db, str(existing_store.id), {
                    "access_token": access_token,
                    "is_active": True,
                    "store_data": shop_info
                })
                store_id = str(existing_store.id)
            else:
                new_store = await crud.create_store(db, {
                    "name": shop_info.get("name", shop),
                    "platform": "shopify",
                    "store_url": shop,
                    "api_key": settings.SHOPIFY_API_KEY,
                    "api_secret": settings.SHOPIFY_API_SECRET,
                    "access_token": access_token,
                    "is_active": True,
                    "store_data": shop_info
                })

                await db.execute(
                    models.store_user_association.insert().values(
                        user_id=user_id,
                        store_id=new_store.id
                    )
                )
                await db.commit()
                store_id = str(new_store.id)

            token = create_access_token(data={"user_id": user_id})
            return RedirectResponse(
                f"{settings.FRONTEND_URL}/connect-success?token={token}&store_id={store_id}&shop={quote(shop)}"
            )

    except Exception as e:
        logger.error(f"Error exchanging code for token: {e}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=exchange_failed")

def validate_hmac(request: Request) -> bool:
    """
    Validate HMAC signature from Shopify.
    """
    if settings.APP_ENV == "development" and settings.DEBUG:
        return True

    try:
        params = dict(request.query_params)
        hmac_value = params.pop("hmac", None)

        if not hmac_value:
            return False

        sorted_params = "&".join([f"{k}={v}" for k, v in sorted(params.items())])

        digest = hmac.new(
            settings.SHOPIFY_API_SECRET.encode('utf-8'),
            sorted_params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(digest, hmac_value)

    except Exception as e:
        logger.error(f"HMAC validation error: {e}")
        return False

async def get_shop_info(shop: str, access_token: str) -> Dict:
    """
    Get shop information from Shopify.
    """
    try:
        api_url = f"https://{shop}/admin/api/2023-10/shop.json"
        headers = {"X-Shopify-Access-Token": access_token}

        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            return response.json().get("shop", {})

    except Exception as e:
        logger.error(f"Error getting shop info: {e}")
        return {}

import json
import secrets
import hmac
import hashlib
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Response
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.config import settings
from app.db.database import get_async_db
from app.db import crud, models
from app.api.routes.auth import create_access_token
from app.api.middleware.security import get_current_user
from app.utils.logger import logger
from app.utils.shopify_debug import shopify_debugger  # Import the debugger

router = APIRouter()

# Store nonce values temporarily (In production, use Redis or similar)
NONCE_STORE = {}

@router.get("/shopify/auth")
async def start_shopify_auth(
    request: Request,  # Add request parameter for logging
    shop: str,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Start Shopify OAuth flow.
    """
    # Log the incoming request
    log_request = await shopify_debugger.log_request(request, "shopify_auth")()
    
    try:
        if not shop.endswith('myshopify.com') and not shop.endswith('shopify.com'):
            error_msg = "Invalid shop domain. Must be a myshopify.com domain."
            logger.error(f"Shopify auth error: {error_msg}")
            
            # Log the error
            shopify_debugger.log_response(
                {"status": "error", "message": error_msg},
                log_id=log_request
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
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
        
        # Log the redirect
        redirect_info = {
            "shop": shop,
            "auth_url": auth_url,
            "nonce": nonce,
            "scopes": scopes,
            "user_id": str(current_user.id)
        }
        shopify_debugger.log_response(redirect_info, log_id=log_request)
        
        return RedirectResponse(auth_url)
        
    except Exception as e:
        # Log any unexpected errors
        shopify_debugger.log_response(
            {"status": "error", "message": str(e)},
            log_id=log_request,
            error=e
        )
        # Re-raise the exception to maintain original behavior
        raise

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
    # Log the incoming request
    log_request = await shopify_debugger.log_request(request, "shopify_callback")()
    
    # Log all parameters
    callback_params = {
        "shop": shop,
        "code_present": bool(code),
        "state": state,
        "query_params": dict(request.query_params),
        "headers": dict(request.headers)
    }
    logger.info(f"Shopify callback received: {json.dumps(callback_params, default=str)}")
    
    if not shop or not code or not state:
        error_msg = f"Missing required parameters: shop={shop}, code={bool(code)}, state={bool(state)}"
        logger.error(error_msg)
        
        # Log the error
        shopify_debugger.log_response(
            {"status": "error", "message": error_msg},
            log_id=log_request
        )
        
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=invalid_request")

    nonce_data = NONCE_STORE.pop(state, None)
    if not nonce_data:
        error_msg = f"Invalid state parameter: {state}"
        logger.error(error_msg)
        
        # Log the error
        shopify_debugger.log_response(
            {"status": "error", "message": error_msg},
            log_id=log_request
        )
        
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=invalid_state")

    if nonce_data["shop"] != shop:
        error_msg = f"Shop mismatch: {nonce_data['shop']} != {shop}"
        logger.error(error_msg)
        
        # Log the error
        shopify_debugger.log_response(
            {"status": "error", "message": error_msg},
            log_id=log_request
        )
        
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=shop_mismatch")

    nonce_timestamp = datetime.fromisoformat(nonce_data["timestamp"])
    if datetime.utcnow() - nonce_timestamp > timedelta(minutes=10):
        error_msg = f"Nonce expired: {nonce_timestamp}"
        logger.error(error_msg)
        
        # Log the error
        shopify_debugger.log_response(
            {"status": "error", "message": error_msg},
            log_id=log_request
        )
        
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=expired_request")

    hmac_valid = validate_hmac(request)
    # Log HMAC validation result
    shopify_debugger.log_api_call(
        method="INTERNAL",
        url="hmac_validation",
        headers={},
        data={"valid": hmac_valid}
    )
    
    if not hmac_valid:
        error_msg = "HMAC validation failed"
        logger.error(error_msg)
        
        # Log the error
        shopify_debugger.log_response(
            {"status": "error", "message": error_msg},
            log_id=log_request
        )
        
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=validation_failed")

    try:
        token_url = f"https://{shop}/admin/oauth/access_token"
        payload = {
            "client_id": settings.SHOPIFY_API_KEY,
            "client_secret": settings.SHOPIFY_API_SECRET,
            "code": code
        }

        # Log token request (pre-call)
        shopify_debugger.log_api_call(
            method="POST",
            url=token_url,
            headers={"Content-Type": "application/json"},
            data={
                "client_id": settings.SHOPIFY_API_KEY,
                "client_secret": "MASKED",
                "code": code
            }
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, json=payload)
            response.raise_for_status()
            token_data = response.json()

            # Log token response (with token masked)
            token_response = {**token_data}
            if "access_token" in token_response:
                token_response["access_token"] = f"{token_response['access_token'][:5]}...MASKED..."
            
            shopify_debugger.log_api_call(
                method="POST",
                url=token_url,
                headers={"Content-Type": "application/json"},
                data={
                    "client_id": settings.SHOPIFY_API_KEY,
                    "client_secret": "MASKED",
                    "code": code
                },
                response=token_response
            )

            access_token = token_data.get("access_token")
            if not access_token:
                error_msg = f"No access token in response: {token_data}"
                logger.error(error_msg)
                
                # Log the error
                shopify_debugger.log_response(
                    {"status": "error", "message": error_msg},
                    log_id=log_request
                )
                
                return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=no_access_token")

            user_id = nonce_data["user_id"]
            shop_info = await get_shop_info(shop, access_token, log_request)  # Pass log_request

            existing_store = None
            user_stores = await crud.get_stores_by_user(db, user_id)
            for store in user_stores:
                if store.store_url == shop:
                    existing_store = store
                    break

            # Log store info
            store_log_data = {
                "shop_info": shop_info,
                "existing_store": bool(existing_store),
                "user_id": user_id
            }
            shopify_debugger.log_api_call(
                method="INTERNAL",
                url="store_processing",
                headers={},
                data=store_log_data
            )

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
            redirect_url = f"{settings.FRONTEND_URL}/connect-success?token={token}&store_id={store_id}&shop={quote(shop)}"
            
            # Log success and redirect
            success_data = {
                "status": "success",
                "store_id": store_id,
                "redirect_url": redirect_url
            }
            shopify_debugger.log_response(success_data, log_id=log_request)
            
            return RedirectResponse(redirect_url)

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e.response.status_code} - {e.response.text}"
        logger.error(f"Error exchanging code for token: {error_msg}")
        
        # Log detailed HTTP error
        shopify_debugger.log_response(
            {
                "status": "error",
                "message": error_msg,
                "status_code": e.response.status_code,
                "response": e.response.text
            },
            log_id=log_request,
            error=e
        )
        
        return RedirectResponse(f"{settings.FRONTEND_URL}/connect-failed?error=exchange_failed")
    except Exception as e:
        error_msg = f"Error exchanging code for token: {e}"
        logger.error(error_msg)
        
        # Log the error
        shopify_debugger.log_response(
            {"status": "error", "message": error_msg},
            log_id=log_request,
            error=e
        )
        
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

        is_valid = hmac.compare_digest(digest, hmac_value)
        logger.info(f"HMAC validation result: {is_valid}")
        return is_valid

    except Exception as e:
        logger.error(f"HMAC validation error: {e}")
        return False

async def get_shop_info(shop: str, access_token: str, log_id: str = None) -> Dict:
    """
    Get shop information from Shopify.
    """
    try:
        api_url = f"https://{shop}/admin/api/2023-10/shop.json"
        headers = {"X-Shopify-Access-Token": access_token}

        # Log shop info request (with token masked)
        if log_id:
            shopify_debugger.log_api_call(
                method="GET",
                url=api_url,
                headers={"X-Shopify-Access-Token": f"{access_token[:5]}...MASKED..."}
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            shop_data = response.json()
            
            # Log shop info response
            if log_id:
                shopify_debugger.log_api_call(
                    method="GET",
                    url=api_url,
                    headers={"X-Shopify-Access-Token": f"{access_token[:5]}...MASKED..."},
                    response=shop_data
                )
            
            return shop_data.get("shop", {})

    except Exception as e:
        logger.error(f"Error getting shop info: {e}")
        
        # Log the error
        if log_id:
            shopify_debugger.log_api_call(
                method="GET",
                url=f"https://{shop}/admin/api/2023-10/shop.json",
                headers={"X-Shopify-Access-Token": f"{access_token[:5]}...MASKED..."},
                error=e
            )
        
        return {}

# Add non-authenticated debug endpoint for testing
if settings.APP_ENV == "development" and settings.DEBUG:
    @router.get("/shopify/auth/debug")
    async def start_shopify_auth_debug(
        request: Request,
        shop: str,
        db: AsyncSession = Depends(get_async_db),
    ):
        """
        Debug version of Shopify OAuth flow without user authentication requirement.
        This is for debugging purposes only and only available in development mode.
        """
        # Log the incoming request
        log_request = await shopify_debugger.log_request(request, "shopify_auth_debug")()
        
        try:
            logger.warning("Using debug endpoint for Shopify auth - NO AUTHENTICATION")
            
            if not shop.endswith('myshopify.com') and not shop.endswith('shopify.com'):
                shop = f"{shop}.myshopify.com"
                logger.info(f"Normalized shop URL to: {shop}")

            # Create a nonce for OAuth flow
            nonce = secrets.token_hex(16)
            NONCE_STORE[nonce] = {
                "user_id": "debug",
                "shop": shop,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Define OAuth scopes
            scopes = [
                "read_products",
                "read_orders",
                "read_customers",
                "read_inventory"
            ]

            # Create the authorization URL
            params = {
                "client_id": settings.SHOPIFY_API_KEY,
                "scope": ",".join(scopes),
                "redirect_uri": f"{settings.APP_URL}/api/shopify/callback/debug",
                "state": nonce
            }
            
            auth_url = f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"
            
            # Log the redirect
            redirect_info = {
                "shop": shop,
                "redirect_url": auth_url,
                "nonce": nonce,
                "scopes": scopes
            }
            shopify_debugger.log_response(redirect_info, log_id=log_request)
            
            return RedirectResponse(auth_url)
            
        except Exception as e:
            # Log the error
            shopify_debugger.log_response(
                {"status": "error", "message": str(e)}, 
                log_id=log_request,
                error=e
            )
            logger.error(f"Error in Shopify auth debug: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Internal Server Error: {str(e)}"}
            )

    @router.get("/shopify/callback/debug")
    async def shopify_callback_debug(
        request: Request,
        shop: Optional[str] = None,
        code: Optional[str] = None,
        state: Optional[str] = None,
        db: AsyncSession = Depends(get_async_db)
    ):
        """
        Debug version of Shopify OAuth callback.
        """
        # Log the incoming request
        log_request = await shopify_debugger.log_request(request, "shopify_callback_debug")()
        
        try:
            logger.warning("Processing debug callback for Shopify auth - NO AUTHENTICATION")
            
            if not shop or not code or not state:
                error_msg = f"Missing required parameters: shop={shop}, code={bool(code)}, state={bool(state)}"
                logger.error(error_msg)
                
                shopify_debugger.log_response(
                    {"status": "error", "message": error_msg},
                    log_id=log_request
                )
                
                return JSONResponse(
                    status_code=400,
                    content={"detail": error_msg}
                )
            
            nonce_data = NONCE_STORE.pop(state, None)
            if not nonce_data:
                error_msg = f"Invalid state parameter: {state}"
                logger.error(error_msg)
                
                shopify_debugger.log_response(
                    {"status": "error", "message": error_msg},
                    log_id=log_request
                )
                
                return JSONResponse(
                    status_code=400,
                    content={"detail": error_msg}
                )

            # Exchange code for access token
            token_url = f"https://{shop}/admin/oauth/access_token"
            payload = {
                "client_id": settings.SHOPIFY_API_KEY,
                "client_secret": settings.SHOPIFY_API_SECRET,
                "code": code
            }

            # Log token request
            shopify_debugger.log_api_call(
                method="POST",
                url=token_url,
                headers={"Content-Type": "application/json"},
                data={"client_id": settings.SHOPIFY_API_KEY, "client_secret": "MASKED", "code": code}
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, json=payload)
                response.raise_for_status()
                token_data = response.json()
                
                # Log token response
                token_response = {**token_data}
                if "access_token" in token_response:
                    token_response["access_token"] = f"{token_response['access_token'][:5]}...MASKED..."
                
                shopify_debugger.log_api_call(
                    method="POST",
                    url=token_url,
                    headers={"Content-Type": "application/json"},
                    data={"client_id": settings.SHOPIFY_API_KEY, "client_secret": "MASKED", "code": code},
                    response=token_response
                )

                access_token = token_data.get("access_token")
                if not access_token:
                    error_msg = f"No access token in response: {token_data}"
                    logger.error(error_msg)
                    
                    shopify_debugger.log_response(
                        {"status": "error", "message": error_msg},
                        log_id=log_request
                    )
                    
                    return JSONResponse(
                        status_code=400,
                        content={"detail": error_msg}
                    )

                # Get shop info
                shop_info = await get_shop_info(shop, access_token, log_request)
                
                # Return success response with debugging info
                success_data = {
                    "status": "success",
                    "message": "Debug OAuth flow completed successfully",
                    "shop": shop,
                    "shop_info": shop_info
                }
                
                shopify_debugger.log_response(success_data, log_id=log_request)
                
                return JSONResponse(content=success_data)
                
        except Exception as e:
            error_msg = f"Unhandled error in Shopify callback debug: {str(e)}"
            logger.error(error_msg)
            
            shopify_debugger.log_response(
                {"status": "error", "message": error_msg},
                log_id=log_request,
                error=e
            )
            
            return JSONResponse(
                status_code=500,
                content={"detail": error_msg}
            )
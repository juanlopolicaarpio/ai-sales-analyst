from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db
from app.db import crud, models
from app.api.routes.auth import get_current_active_user
from app.core.shopify_client import ShopifyClient
from app.utils.logger import logger

router = APIRouter()

class StoreBase(BaseModel):
    name: str
    platform: str
    store_url: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None

class StoreCreate(StoreBase):
    pass

class StoreResponse(StoreBase):
    id: str
    is_active: bool
    
    class Config:
        orm_mode = True

class StoreWithConnectionStatus(StoreResponse):
    connection_status: str

@router.post("/stores", response_model=StoreResponse)
async def create_store(
    store_data: StoreCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_active_user)
):
    """Create a new store and connect it to the current user."""
    
    # Create the store
    new_store = await crud.create_store(db, {
        "name": store_data.name,
        "platform": store_data.platform,
        "store_url": store_data.store_url,
        "api_key": store_data.api_key,
        "api_secret": store_data.api_secret,
        "access_token": store_data.access_token,
        "is_active": True
    })
    
    # Connect store to user (using raw SQL since we don't have a CRUD function for this)
    await db.execute(
        models.store_user_association.insert().values(
            user_id=current_user.id,
            store_id=new_store.id
        )
    )
    await db.commit()
    
    # Test connection to verify credentials
    if store_data.platform.lower() == "shopify":
        try:
            client = ShopifyClient(new_store)
            await client.get_shop_info()
            logger.info(f"Successfully connected to Shopify store: {new_store.name}")
        except Exception as e:
            logger.error(f"Error connecting to Shopify store: {e}")
            # Don't fail the request, just log the error
    
    return new_store

@router.get("/stores", response_model=List[StoreResponse])
async def get_user_stores(
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_active_user)
):
    """Get all stores for the current user."""
    stores = await crud.get_stores_by_user(db, str(current_user.id))
    return stores

@router.get("/stores/{store_id}", response_model=StoreWithConnectionStatus)
async def get_store(
    store_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_active_user)
):
    """Get a specific store by ID."""
    # Get the store
    store = await crud.get_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Check if user has access to this store
    user_stores = await crud.get_stores_by_user(db, str(current_user.id))
    if store not in user_stores:
        raise HTTPException(status_code=403, detail="Not authorized to access this store")
    
    # Test connection
    connection_status = "unknown"
    if store.platform.lower() == "shopify":
        try:
            client = ShopifyClient(store)
            await client.get_shop_info()
            connection_status = "connected"
        except Exception as e:
            logger.error(f"Error connecting to Shopify store: {e}")
            connection_status = "error"
    
    # Convert to response model and add connection status
    response = StoreWithConnectionStatus(
        id=str(store.id),
        name=store.name,
        platform=store.platform,
        store_url=store.store_url,
        api_key=store.api_key,
        api_secret=store.api_secret,
        access_token=store.access_token,
        is_active=store.is_active,
        connection_status=connection_status
    )
    
    return response

@router.put("/stores/{store_id}", response_model=StoreResponse)
async def update_store(
    store_id: str,
    store_data: StoreBase,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_active_user)
):
    """Update a store."""
    # Check if store exists and user has access
    store = await crud.get_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    user_stores = await crud.get_stores_by_user(db, str(current_user.id))
    if store not in user_stores:
        raise HTTPException(status_code=403, detail="Not authorized to modify this store")
    
    # Update the store
    updated_store = await crud.update_store(db, store_id, {
        "name": store_data.name,
        "platform": store_data.platform,
        "store_url": store_data.store_url,
        "api_key": store_data.api_key,
        "api_secret": store_data.api_secret,
        "access_token": store_data.access_token
    })
    
    return updated_store

@router.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_store(
    store_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_active_user)
):
    """Delete a store or remove user's access to it."""
    # Check if store exists and user has access
    store = await crud.get_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    user_stores = await crud.get_stores_by_user(db, str(current_user.id))
    if store not in user_stores:
        raise HTTPException(status_code=403, detail="Not authorized to delete this store")
    
    # Instead of deleting the store completely, just disconnect it from the user
    await db.execute(
        models.store_user_association.delete().where(
            (models.store_user_association.c.user_id == current_user.id) &
            (models.store_user_association.c.store_id == store_id)
        )
    )
    await db.commit()
    
    # Check if any users are still connected to the store
    stmt = models.store_user_association.select().where(
        models.store_user_association.c.store_id == store_id
    )
    result = await db.execute(stmt)
    associations = result.fetchall()
    
    # If no users are connected, mark the store as inactive
    if not associations:
        await crud.update_store(db, store_id, {"is_active": False})
    
    return None

@router.post("/stores/{store_id}/test-connection", response_model=dict)
async def test_store_connection(
    store_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_active_user)
):
    """Test the connection to a store."""
    # Check if store exists and user has access
    store = await crud.get_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    user_stores = await crud.get_stores_by_user(db, str(current_user.id))
    if store not in user_stores:
        raise HTTPException(status_code=403, detail="Not authorized to access this store")
    
    # Test connection based on platform
    if store.platform.lower() == "shopify":
        try:
            client = ShopifyClient(store)
            shop_info = await client.get_shop_info()
            
            return {
                "status": "success",
                "message": f"Successfully connected to {store.name}",
                "shop_info": {
                    "name": shop_info.get("shop", {}).get("name"),
                    "domain": shop_info.get("shop", {}).get("domain"),
                    "email": shop_info.get("shop", {}).get("email"),
                    "country": shop_info.get("shop", {}).get("country_name")
                }
            }
        except Exception as e:
            logger.error(f"Error connecting to Shopify store: {e}")
            return {
                "status": "error",
                "message": f"Failed to connect to Shopify store: {str(e)}"
            }
    else:
        return {
            "status": "unknown",
            "message": f"Testing not implemented for platform: {store.platform}"
        }
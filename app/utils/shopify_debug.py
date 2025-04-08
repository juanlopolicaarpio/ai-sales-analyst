import os
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

import httpx
from fastapi import Request, Response
from loguru import logger

# Create debug logs directory
DEBUG_DIR = Path("logs/shopify_debug")
DEBUG_DIR.mkdir(exist_ok=True, parents=True)

class ShopifyDebugger:
    """
    Comprehensive Shopify integration debugger that logs all relevant information
    about Shopify authentication flows and API calls.
    """
    
    @staticmethod
    def log_request(
        request: Request, 
        source: str = "shopify_auth", 
        include_headers: bool = True,
        mask_sensitive: bool = True
    ) -> str:
        """
        Log details of an incoming request.
        
        Args:
            request: The FastAPI request object
            source: Source identifier for the log
            include_headers: Whether to include headers in the log
            mask_sensitive: Whether to mask sensitive data
            
        Returns:
            str: ID of the generated log
        """
        log_id = f"{int(time.time())}_{source}"
        log_file = DEBUG_DIR / f"{log_id}_request.json"
        
        async def get_body():
            body = await request.body()
            try:
                return json.loads(body)
            except:
                # Handle case where body isn't JSON
                return body.decode("utf-8", errors="replace")
        
        # Will execute this in the route handler
        async def _log_request():
            try:
                headers = dict(request.headers) if include_headers else {}
                
                # Mask sensitive data if needed
                if mask_sensitive and include_headers:
                    for key in headers:
                        if key.lower() in ("authorization", "cookie", "x-csrf"):
                            headers[key] = f"{headers[key][:10]}...MASKED..."
                
                # Get query params
                params = dict(request.query_params)
                
                # Get request body (awaited inside the route handler)
                body = await get_body()
                
                log_data = {
                    "timestamp": datetime.now().isoformat(),
                    "source": source,
                    "method": request.method,
                    "url": str(request.url),
                    "client": {
                        "host": request.client.host if request.client else None,
                        "headers": headers
                    },
                    "query_params": params,
                    "body": body,
                }
                
                with open(log_file, "w") as f:
                    json.dump(log_data, f, indent=2, default=str)
                
                logger.info(f"Shopify debug request logged: {log_file}")
                
            except Exception as e:
                logger.error(f"Error logging Shopify request: {e}")
                with open(log_file, "w") as f:
                    json.dump({
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }, f, indent=2)
            
            return log_id
        
        # Return the coroutine to be awaited in the request handler
        return _log_request
    
    @staticmethod
    def log_response(
        response: Union[Response, Dict, Any], 
        log_id: str,
        error: Optional[Exception] = None
    ):
        """
        Log details of a response or error.
        
        Args:
            response: The response object or data to log
            log_id: ID from the log_request call
            error: Optional exception that occurred
        """
        log_file = DEBUG_DIR / f"{log_id}_response.json"
        
        try:
            response_data = {}
            
            # Handle different response types
            if isinstance(response, Response):
                response_data = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.body.decode("utf-8", errors="replace") if hasattr(response, "body") else None
                }
            elif isinstance(response, dict):
                response_data = response
            else:
                response_data = {"data": str(response)}
            
            # Add error info if present
            if error:
                response_data["error"] = {
                    "type": error.__class__.__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc()
                }
            
            # Add timestamp
            response_data["timestamp"] = datetime.now().isoformat()
            
            with open(log_file, "w") as f:
                json.dump(response_data, f, indent=2, default=str)
            
            logger.info(f"Shopify debug response logged: {log_file}")
            
        except Exception as e:
            logger.error(f"Error logging Shopify response: {e}")
            with open(log_file, "w") as f:
                json.dump({
                    "meta_error": str(e),
                    "original_error": str(error) if error else None,
                    "traceback": traceback.format_exc()
                }, f, indent=2)
    
    @staticmethod
    def log_api_call(
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        response: Optional[Any] = None,
        error: Optional[Exception] = None
    ):
        """
        Log details of a Shopify API call.
        
        Args:
            method: HTTP method used
            url: URL of the API endpoint
            headers: Request headers
            params: Request query parameters
            data: Request payload
            response: Response from the API call
            error: Any exception that occurred
        """
        log_id = f"{int(time.time())}_api_call"
        log_file = DEBUG_DIR / f"{log_id}.json"
        
        try:
            # Mask sensitive headers
            masked_headers = dict(headers)
            for key in masked_headers:
                if key.lower() in ("authorization", "x-shopify-access-token"):
                    masked_headers[key] = f"{masked_headers[key][:10]}...MASKED..."
            
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "method": method,
                "url": url,
                "headers": masked_headers,
                "params": params,
                "data": data
            }
            
            # Add response if available
            if response is not None:
                if hasattr(response, "status_code"):
                    # httpx Response or similar
                    log_data["response"] = {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "content": response.text if hasattr(response, "text") else str(response),
                    }
                    # Try to parse JSON response
                    try:
                        log_data["response"]["json"] = response.json()
                    except:
                        pass
                else:
                    # Generic response
                    log_data["response"] = response
            
            # Add error info if present
            if error:
                log_data["error"] = {
                    "type": error.__class__.__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc()
                }
            
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2, default=str)
            
            logger.info(f"Shopify API call logged: {log_file}")
            
        except Exception as e:
            logger.error(f"Error logging Shopify API call: {e}")
            with open(log_file, "w") as f:
                json.dump({
                    "meta_error": str(e),
                    "original_error": str(error) if error else None,
                    "traceback": traceback.format_exc()
                }, f, indent=2)

# Create a singleton instance
shopify_debugger = ShopifyDebugger()
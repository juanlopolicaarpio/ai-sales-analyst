import requests
import json
import time
import sys

# API base URL - make sure this matches where your FastAPI application is running
API_URL = "http://localhost:8000/api"

# Step 1: Register a user
def register_user():
    try:
        print(f"Attempting to register user at {API_URL}/register")
        response = requests.post(
            f"{API_URL}/register",
            json={
                "email": "testuser@example.com",
                "password": "securepassword123",
                "full_name": "Test User",
                "slack_user_id": "U01234ABCDE",
                "whatsapp_number": "+1234567890"
            },
            timeout=10  # Add a timeout to prevent hanging
        )
        
        # Check if request was successful
        response.raise_for_status()
        print("Registration Response:", response.json())
        return response.json().get("access_token")
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: Could not connect to the API server at {API_URL}")
        print(f"Make sure your FastAPI server is running at {API_URL}")
        print(f"Connection error details: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print("Response content:", response.text)
        return None
    except requests.exceptions.Timeout:
        print("Request timed out. The server might be overloaded or not responding.")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

# Step 2: Connect a store
def connect_store(token):
    if not token:
        print("No token available for store connection")
        return None
        
    try:
        print(f"Attempting to connect store at {API_URL}/stores")
        response = requests.post(
            f"{API_URL}/stores",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "My Test Store",
                "platform": "shopify",
                "store_url": "your-store.myshopify.com",
                "api_key": "your-api-key",
                "api_secret": "your-api-secret",
                "access_token": "your-access-token"
            },
            timeout=10
        )
        
        # Check if request was successful
        response.raise_for_status()
        print("Store Connection Response:", response.json())
        return response.json().get("id")
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: Could not connect to the API server at {API_URL}/stores")
        print(f"Connection error details: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print("Response content:", response.text)
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

# Step 3: Update preferences
def set_preferences(token):
    if not token:
        print("No token available for setting preferences")
        return False
        
    try:
        print(f"Attempting to update preferences at {API_URL}/preferences")
        response = requests.put(
            f"{API_URL}/preferences",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "notification_channel": "email",
                "timezone": "America/New_York",
                "notification_preferences": {
                    "sales_alerts": True,
                    "anomaly_detection": True,
                    "daily_summary": True
                }
            },
            timeout=10
        )
        
        # Check if request was successful
        response.raise_for_status()
        print("Preferences Update Response:", response.json())
        return True
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: Could not connect to the API server at {API_URL}/preferences")
        print(f"Connection error details: {e}")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print("Response content:", response.text)
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

# Step 4: Test notification
def test_notification(token):
    if not token:
        print("No token available for testing notification")
        return False
        
    try:
        print(f"Attempting to test notification at {API_URL}/preferences/test-notification")
        response = requests.post(
            f"{API_URL}/preferences/test-notification",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        # Check if request was successful
        response.raise_for_status()
        print("Test Notification Response:", response.json())
        return True
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: Could not connect to the API server at {API_URL}/preferences/test-notification")
        print(f"Connection error details: {e}")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print("Response content:", response.text)
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

# Main test flow
def run_tests():
    print("=" * 50)
    print("Starting API Tests")
    print("=" * 50)
    
    # Check if server is reachable before running tests
    try:
        health_check = requests.get(f"{API_URL}/health", timeout=5)
        print(f"Server health check: {health_check.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot reach API server at {API_URL}")
        print("Make sure your FastAPI server is running and accessible.")
        print("Common issues:")
        print("1. FastAPI server is not started")
        print("2. Server is running on a different host/port")
        print("3. Firewall blocking the connection")
        print("4. Network issues")
        return
    except Exception as e:
        print(f"Health check failed: {e}")
        print("Continuing with tests anyway...")
    
    # Register and get token
    print("\n[1/4] Testing user registration...")
    token = register_user()
    if not token:
        print("⚠️ Registration failed, cannot continue tests")
        return
    print("✓ Registration successful")
    
    # Wait a bit for registration to process
    time.sleep(1)
    
    # Connect store
    print("\n[2/4] Testing store connection...")
    store_id = connect_store(token)
    if not store_id:
        print("⚠️ Store connection failed, cannot continue tests")
        return
    print("✓ Store connection successful")
    
    # Set preferences
    print("\n[3/4] Testing preference update...")
    if set_preferences(token):
        print("✓ Preference update successful")
    else:
        print("⚠️ Preference update failed")
    
    # Test notification
    print("\n[4/4] Testing notification...")
    if test_notification(token):
        print("✓ Test notification successful")
    else:
        print("⚠️ Test notification failed")
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)

if __name__ == "__main__":
    run_tests()
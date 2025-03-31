# test_system.py
import requests
import json
import time

# API base URL
API_URL = "http://localhost:8000/api"

# Step 1: Register a user
def register_user():
    response = requests.post(
        f"{API_URL}/register",
        json={
            "email": "testuser@example.com",
            "password": "securepassword123",
            "full_name": "Test User",
            "slack_user_id": "U01234ABCDE",
            "whatsapp_number": "+1234567890"
        }
    )
    print("Registration Response:", response.json())
    return response.json().get("access_token")

# Step 2: Connect a store
def connect_store(token):
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
        }
    )
    print("Store Connection Response:", response.json())
    return response.json().get("id")

# Step 3: Update preferences
def set_preferences(token):
    response = requests.put(
        f"{API_URL}/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "notification_channel": "email",
            "timezone": "America/New_York"
        }
    )
    print("Preferences Update Response:", response.json())

# Step 4: Test notification
def test_notification(token):
    response = requests.post(
        f"{API_URL}/preferences/test-notification",
        headers={"Authorization": f"Bearer {token}"}
    )
    print("Test Notification Response:", response.json())

# Main test flow
def run_tests():
    # Register and get token
    token = register_user()
    if not token:
        print("Registration failed, cannot continue tests")
        return
    
    # Wait a bit for registration to process
    time.sleep(1)
    
    # Connect store
    store_id = connect_store(token)
    if not store_id:
        print("Store connection failed, cannot continue tests")
        return
    
    # Set preferences
    set_preferences(token)
    
    # Test notification
    test_notification(token)
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    run_tests()
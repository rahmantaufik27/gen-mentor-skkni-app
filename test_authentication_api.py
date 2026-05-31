"""
API Testing Script for Authentication Module
Test all authentication endpoints without using the frontend UI.
"""

import requests
import json
import sys
from typing import Dict, Any


BASE_URL = "http://localhost:5000"
TEST_RESULTS = []


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def print_request(method: str, endpoint: str, data: Dict = None):
    """Print request details."""
    print(f"\n📤 REQUEST: {method} {endpoint}")
    if data:
        print(f"Body: {json.dumps(data, indent=2)}")


def print_response(response: requests.Response):
    """Print response details."""
    print(f"\n📥 RESPONSE: {response.status_code}")
    try:
        data = response.json()
        print(f"Body: {json.dumps(data, indent=2)}")
    except:
        print(f"Body: {response.text}")


def test_endpoint(name: str, method: str, endpoint: str, data: Dict = None) -> bool:
    """Test an API endpoint."""
    try:
        url = f"{BASE_URL}{endpoint}"
        print_request(method, endpoint, data)
        
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        else:
            print(f"❌ Unknown method: {method}")
            return False
        
        print_response(response)
        
        success = response.status_code < 400
        TEST_RESULTS.append({
            "name": name,
            "status": "✓ PASS" if success else "❌ FAIL",
            "code": response.status_code
        })
        
        return success, response
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Cannot connect to {BASE_URL}")
        print("Make sure the backend server is running on localhost:5000")
        TEST_RESULTS.append({"name": name, "status": "❌ FAIL", "code": "Connection Error"})
        return False, None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        TEST_RESULTS.append({"name": name, "status": "❌ FAIL", "code": str(e)})
        return False, None


def main():
    """Run all tests."""
    print_header("Authentication API Test Suite")
    print(f"Testing: {BASE_URL}")
    
    # Test 1: Check backend is running
    print_header("Test 1: Backend Health Check")
    try:
        response = requests.get(f"{BASE_URL}/")
        print_response(response)
        if response.status_code != 200:
            print("\n❌ Backend is not responding correctly!")
            return False
        print("✓ Backend is running")
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to {BASE_URL}")
        print("Make sure to start the backend server:")
        print("  cd backend/")
        print("  python app.py")
        return False
    
    # Test 2: Register a new user
    print_header("Test 2: User Registration")
    test_email = "testuser@example.com"
    register_data = {
        "full_name": "Test User",
        "email": test_email,
        "password": "TestPassword123",
        "confirm_password": "TestPassword123"
    }
    success, register_response = test_endpoint(
        "Register User",
        "POST",
        "/api/auth/register",
        register_data
    )
    
    if not success:
        print("\n❌ Registration failed!")
        print("Possible causes:")
        print("  1. Email already registered - try with a different email")
        print("  2. Database not initialized - run setup_authentication.py")
        print("  3. Backend not running - start with: python app.py")
        return False
    
    user_id = None
    try:
        user_id = register_response.json().get("user_id")
        print(f"\n✓ User registered successfully")
        print(f"  User ID: {user_id}")
    except:
        print("\n❌ Could not extract user_id from response")
    
    # Test 3: Try duplicate registration
    print_header("Test 3: Duplicate Email Check")
    duplicate_data = {
        "full_name": "Another User",
        "email": test_email,
        "password": "Password123",
        "confirm_password": "Password123"
    }
    success, _ = test_endpoint(
        "Duplicate Registration",
        "POST",
        "/api/auth/register",
        duplicate_data
    )
    
    if success:
        print("\n❌ Duplicate registration was allowed (should have been blocked)!")
    else:
        print("\n✓ Duplicate email correctly rejected")
    
    # Test 4: Invalid password length
    print_header("Test 4: Password Validation")
    invalid_pwd_data = {
        "full_name": "Test User",
        "email": "short@example.com",
        "password": "short",
        "confirm_password": "short"
    }
    success, _ = test_endpoint(
        "Short Password",
        "POST",
        "/api/auth/register",
        invalid_pwd_data
    )
    
    if success:
        print("\n❌ Short password was accepted (should have been rejected)!")
    else:
        print("\n✓ Short password correctly rejected")
    
    # Test 5: Password mismatch
    print_header("Test 5: Password Confirmation")
    mismatch_data = {
        "full_name": "Test User",
        "email": "mismatch@example.com",
        "password": "Password123",
        "confirm_password": "DifferentPassword123"
    }
    success, _ = test_endpoint(
        "Password Mismatch",
        "POST",
        "/api/auth/register",
        mismatch_data
    )
    
    if success:
        print("\n❌ Mismatched passwords were accepted (should have been rejected)!")
    else:
        print("\n✓ Password mismatch correctly rejected")
    
    # Test 6: Login with correct credentials
    print_header("Test 6: User Login (Valid Credentials)")
    login_data = {
        "email": test_email,
        "password": "TestPassword123"
    }
    success, login_response = test_endpoint(
        "Valid Login",
        "POST",
        "/api/auth/login",
        login_data
    )
    
    if not success:
        print("\n❌ Login failed with valid credentials!")
        return False
    
    print("\n✓ Login successful")
    
    # Test 7: Login with wrong password
    print_header("Test 7: User Login (Invalid Password)")
    wrong_pwd_data = {
        "email": test_email,
        "password": "WrongPassword"
    }
    success, _ = test_endpoint(
        "Invalid Password",
        "POST",
        "/api/auth/login",
        wrong_pwd_data
    )
    
    if success:
        print("\n❌ Login with wrong password was allowed!")
    else:
        print("\n✓ Wrong password correctly rejected")
    
    # Test 8: Login with non-existent email
    print_header("Test 8: User Login (Non-existent Email)")
    nonexistent_data = {
        "email": "nonexistent@example.com",
        "password": "SomePassword"
    }
    success, _ = test_endpoint(
        "Non-existent Email",
        "POST",
        "/api/auth/login",
        nonexistent_data
    )
    
    if success:
        print("\n❌ Login with non-existent email was allowed!")
    else:
        print("\n✓ Non-existent email correctly rejected")
    
    # Test 9: Get current user
    print_header("Test 9: Get Current User")
    success, _ = test_endpoint(
        "Get Current User",
        "GET",
        "/api/auth/me"
    )
    
    if not success:
        print("\n⚠️  User not found - this is expected if session is not active")
        print("   In a real scenario, you would get session from login first")
    
    # Test 10: Logout
    print_header("Test 10: User Logout")
    success, _ = test_endpoint(
        "Logout",
        "POST",
        "/api/auth/logout"
    )
    
    if success:
        print("\n✓ Logout successful")
    else:
        print("\n❌ Logout failed")
    
    # Print test summary
    print_header("Test Summary")
    print(f"\nTotal Tests: {len(TEST_RESULTS)}")
    
    passed = sum(1 for t in TEST_RESULTS if "PASS" in t["status"])
    failed = sum(1 for t in TEST_RESULTS if "FAIL" in t["status"])
    
    print(f"Passed: {passed}")
    print(f"Failed: {failed}\n")
    
    for result in TEST_RESULTS:
        print(f"  {result['status']}: {result['name']} (HTTP {result['code']})")
    
    print("\n" + "="*70)
    if failed == 0:
        print("✓ All tests passed!")
        print("="*70 + "\n")
        return True
    else:
        print(f"❌ {failed} test(s) failed!")
        print("="*70 + "\n")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

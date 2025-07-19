#!/usr/bin/env python3
"""
Backend API Testing for Vinted Relist App
Tests all backend endpoints with real Vinted API integration
"""

import requests
import json
import time
from datetime import datetime

# Test Configuration
BASE_URL = "https://71a6384c-dbac-4f3d-9477-f77308da3435.preview.emergentagent.com/api"
CSRF_TOKEN = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
AUTH_TOKEN = "eyJraWQiOiJFNTdZZHJ1SHBsQWp1MmNObzFEb3JIM2oyN0J1NS1zX09QNVB3UGlobjVNIiwiYWxnIjoiUFMyNTYifQ.eyJhcHBfaWQiOjQsImNsaWVudF9pZCI6IndlYiIsImF1ZCI6ImZyLmNvcmUuYXBpIiwiaXNzIjoidmludGVkLWlhbS1zZXJ2aWNlIiwic3ViIjoiMjgwNTMzMTQxIiwiaWF0IjoxNzUyOTU4MjM0LCJzaWQiOiIyMTcxNjI3ZC0xNzUyOTU4MjM0Iiwic2NvcGUiOiJ1c2VyIiwiZXhwIjoxNzUzNTYzMDM0LCJwdXJwb3NlIjoicmVmcmVzaCIsImxvZ2luX3R5cGUiOjMsImFjdCI6eyJzdWIiOiIyODA1MzMxNDEifSwiYWNjb3VudF9pZCI6MjIxNTA2MTAxfQ.SxJUdeMCNgbpdISUeJwj8cL2b8HGso9GgUe96Q4P4UZoaeP0qvjzs1A3qAXM08BtpXLLfClHjAa4Rs1B8hQbmNtxtQTRN0ceNzqeQ7G9sk0HizPD6btHJ1WmBAktCYZPPk7tkEm8Np4y8Tq2FO68dFGXWT5UB6D4Hur5xalfOkHtsHmdlE0LCxb8jlGICwNRdIzaOkrT_P8h3Rs7_oaKT2FUvkT4L1MF6mpbYZf8Ag-DoYGEsqTfQ8sZZqSqhkrT8n_QovyYeZhZXKzpm-ky3GmmSfya5_vXOrK8t8Q59yiBMmy_Zdf7KQ1uzd3e4tG16pWZaBj0uHyH4NyRtxPEcw"
TEST_USER_ID = "248331973"

# Global variables for test state
user_token = None
imported_products = []

class TestResults:
    def __init__(self):
        self.results = {}
        self.errors = []
    
    def add_result(self, test_name, success, message, details=None):
        self.results[test_name] = {
            'success': success,
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        if not success:
            self.errors.append(f"{test_name}: {message}")
    
    def print_summary(self):
        print("\n" + "="*80)
        print("BACKEND API TEST RESULTS SUMMARY")
        print("="*80)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\nDETAILED RESULTS:")
        print("-" * 50)
        
        for test_name, result in self.results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"{status} {test_name}")
            print(f"    Message: {result['message']}")
            if result['details']:
                print(f"    Details: {result['details']}")
            print()
        
        if self.errors:
            print("CRITICAL ERRORS:")
            print("-" * 50)
            for error in self.errors:
                print(f"❌ {error}")

def make_request(method, endpoint, data=None, headers=None, auth_token=None):
    """Helper function to make HTTP requests"""
    url = f"{BASE_URL}{endpoint}"
    
    request_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    if headers:
        request_headers.update(headers)
    
    if auth_token:
        request_headers['Authorization'] = f'Bearer {auth_token}'
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=request_headers, timeout=30)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, headers=request_headers, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def test_authentication():
    """Test 1: User Authentication System"""
    print("Testing Authentication Endpoint...")
    
    # Test login with valid credentials
    login_data = {
        "csrf_token": CSRF_TOKEN,
        "auth_token": AUTH_TOKEN
    }
    
    response = make_request('POST', '/auth/login', data=login_data)
    
    if response is None:
        results.add_result("Authentication", False, "Failed to connect to authentication endpoint")
        return None
    
    if response.status_code == 200:
        try:
            response_data = response.json()
            if 'user_id' in response_data:
                user_id = response_data['user_id']
                results.add_result("Authentication", True, f"Login successful, user_id: {user_id}", response_data)
                return user_id
            else:
                results.add_result("Authentication", False, "Login response missing user_id", response_data)
                return None
        except json.JSONDecodeError:
            results.add_result("Authentication", False, "Invalid JSON response from login", response.text)
            return None
    else:
        results.add_result("Authentication", False, f"Login failed with status {response.status_code}", response.text)
        return None

def test_product_import(user_token):
    """Test 2: Product Import Functionality"""
    print("Testing Product Import Endpoint...")
    
    if not user_token:
        results.add_result("Product Import", False, "Cannot test import - no valid user token")
        return []
    
    response = make_request('GET', f'/products/import/{TEST_USER_ID}', auth_token=user_token)
    
    if response is None:
        results.add_result("Product Import", False, "Failed to connect to import endpoint")
        return []
    
    if response.status_code == 200:
        try:
            response_data = response.json()
            if 'count' in response_data:
                count = response_data['count']
                results.add_result("Product Import", True, f"Import successful, imported {count} products", response_data)
                return response_data
            else:
                results.add_result("Product Import", False, "Import response missing count field", response_data)
                return []
        except json.JSONDecodeError:
            results.add_result("Product Import", False, "Invalid JSON response from import", response.text)
            return []
    else:
        results.add_result("Product Import", False, f"Import failed with status {response.status_code}", response.text)
        return []

def test_get_products(user_token):
    """Test 3: Get Products API"""
    print("Testing Get Products Endpoint...")
    
    if not user_token:
        results.add_result("Get Products", False, "Cannot test get products - no valid user token")
        return []
    
    response = make_request('GET', '/products', auth_token=user_token)
    
    if response is None:
        results.add_result("Get Products", False, "Failed to connect to products endpoint")
        return []
    
    if response.status_code == 200:
        try:
            products = response.json()
            if isinstance(products, list):
                results.add_result("Get Products", True, f"Retrieved {len(products)} products", f"First product: {products[0] if products else 'No products'}")
                return products
            else:
                results.add_result("Get Products", False, "Products response is not a list", products)
                return []
        except json.JSONDecodeError:
            results.add_result("Get Products", False, "Invalid JSON response from products", response.text)
            return []
    else:
        results.add_result("Get Products", False, f"Get products failed with status {response.status_code}", response.text)
        return []

def test_product_relist(user_token, products):
    """Test 4: Product Relist Functionality"""
    print("Testing Product Relist Endpoint...")
    
    if not user_token:
        results.add_result("Product Relist", False, "Cannot test relist - no valid user token")
        return
    
    if not products:
        results.add_result("Product Relist", False, "Cannot test relist - no products available")
        return
    
    # Test with first product (if available)
    product_ids = [products[0]['id']] if products else []
    
    if not product_ids:
        results.add_result("Product Relist", False, "No product IDs available for relist test")
        return
    
    relist_data = {
        "product_ids": product_ids
    }
    
    response = make_request('POST', '/products/relist', data=relist_data, auth_token=user_token)
    
    if response is None:
        results.add_result("Product Relist", False, "Failed to connect to relist endpoint")
        return
    
    if response.status_code == 200:
        try:
            response_data = response.json()
            if 'results' in response_data:
                results.add_result("Product Relist", True, f"Relist completed: {response_data['message']}", response_data)
            else:
                results.add_result("Product Relist", False, "Relist response missing results field", response_data)
        except json.JSONDecodeError:
            results.add_result("Product Relist", False, "Invalid JSON response from relist", response.text)
    else:
        results.add_result("Product Relist", False, f"Relist failed with status {response.status_code}", response.text)

def test_dashboard_stats(user_token):
    """Test 5: Dashboard Statistics API"""
    print("Testing Dashboard Stats Endpoint...")
    
    if not user_token:
        results.add_result("Dashboard Stats", False, "Cannot test dashboard stats - no valid user token")
        return
    
    response = make_request('GET', '/dashboard/stats', auth_token=user_token)
    
    if response is None:
        results.add_result("Dashboard Stats", False, "Failed to connect to dashboard stats endpoint")
        return
    
    if response.status_code == 200:
        try:
            stats_data = response.json()
            required_fields = ['total_products', 'active_products', 'sold_products', 'total_revenue', 'total_views']
            
            missing_fields = [field for field in required_fields if field not in stats_data]
            
            if not missing_fields:
                results.add_result("Dashboard Stats", True, f"Dashboard stats retrieved successfully", stats_data)
            else:
                results.add_result("Dashboard Stats", False, f"Dashboard stats missing fields: {missing_fields}", stats_data)
        except json.JSONDecodeError:
            results.add_result("Dashboard Stats", False, "Invalid JSON response from dashboard stats", response.text)
    else:
        results.add_result("Dashboard Stats", False, f"Dashboard stats failed with status {response.status_code}", response.text)

def test_invalid_authentication():
    """Test 6: Invalid Authentication Handling"""
    print("Testing Invalid Authentication Handling...")
    
    # Test with invalid token
    response = make_request('GET', '/products', auth_token='invalid_token')
    
    if response is None:
        results.add_result("Invalid Auth Handling", False, "Failed to connect for invalid auth test")
        return
    
    if response.status_code == 401:
        results.add_result("Invalid Auth Handling", True, "Correctly rejected invalid authentication")
    else:
        results.add_result("Invalid Auth Handling", False, f"Expected 401 for invalid auth, got {response.status_code}")

def run_all_tests():
    """Run all backend tests in priority order"""
    global user_token, imported_products
    
    print("Starting Backend API Tests...")
    print(f"Base URL: {BASE_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print("="*80)
    
    # Test 1: Authentication (HIGH priority)
    user_token = test_authentication()
    time.sleep(1)  # Brief pause between tests
    
    # Test 2: Product Import (HIGH priority)
    import_result = test_product_import(user_token)
    time.sleep(2)  # Longer pause for import operation
    
    # Test 3: Get Products (MEDIUM priority)
    products = test_get_products(user_token)
    time.sleep(1)
    
    # Test 4: Product Relist (HIGH priority)
    test_product_relist(user_token, products)
    time.sleep(1)
    
    # Test 5: Dashboard Stats (MEDIUM priority)
    test_dashboard_stats(user_token)
    time.sleep(1)
    
    # Test 6: Invalid Authentication
    test_invalid_authentication()
    
    # Print comprehensive results
    results.print_summary()

if __name__ == "__main__":
    results = TestResults()
    run_all_tests()
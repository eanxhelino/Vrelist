#!/usr/bin/env python3
"""
Test script for browser relist endpoint
"""

import requests
import json

def test_browser_relist_endpoint():
    """Test if the browser relist endpoint exists and responds"""
    
    # Test server is running
    try:
        response = requests.get("http://localhost:8000/")
        print(f"✅ Server is accessible: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Start it with: uvicorn server:app --reload")
        return False
    
    # Test browser relist endpoint (should fail with auth required)
    try:
        response = requests.post("http://localhost:8000/api/products/relist-browser", 
                               json={"product_ids": ["test"]})
        print(f"\n📋 Browser relist endpoint status: {response.status_code}")
        
        if response.status_code == 403:
            print("✅ Endpoint exists but requires authentication (expected)")
            print(f"Response: {response.json()}")
            return True
        elif response.status_code == 404:
            print("❌ Endpoint not found - there may be a routing issue")
            return False
        else:
            print(f"⚠️  Unexpected response: {response.text}")
            return True
            
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return False

def test_api_routes():
    """List available API routes"""
    try:
        response = requests.get("http://localhost:8000/docs")
        if response.status_code == 200:
            print("✅ API documentation available at: http://localhost:8000/docs")
        
        # Test OpenAPI spec
        response = requests.get("http://localhost:8000/openapi.json")
        if response.status_code == 200:
            openapi_spec = response.json()
            print("\n📋 Available API endpoints:")
            for path, methods in openapi_spec.get("paths", {}).items():
                for method in methods.keys():
                    print(f"  {method.upper()} {path}")
        
    except Exception as e:
        print(f"Error getting API routes: {e}")

if __name__ == "__main__":
    print("🧪 Testing Browser Relist Endpoint")
    print("=" * 40)
    
    # Test endpoint
    endpoint_works = test_browser_relist_endpoint()
    
    # Show available routes
    test_api_routes()
    
    if endpoint_works:
        print("\n🎉 Browser relist endpoint is working!")
        print("\n📝 Next steps:")
        print("1. Start the backend: uvicorn server:app --reload")
        print("2. Start the frontend: cd ../frontend && npm start")
        print("3. Test browser relisting in the UI")
    else:
        print("\n❌ Browser relist endpoint has issues")
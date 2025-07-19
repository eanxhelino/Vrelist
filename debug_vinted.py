#!/usr/bin/env python3
"""
Direct Vinted API Test to debug the 401 error
"""

import httpx
import asyncio
import json

# Test Configuration
CSRF_TOKEN = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
AUTH_TOKEN = "eyJraWQiOiJFNTdZZHJ1SHBsQWp1MmNObzFEb3JIM2oyN0J1NS1zX09QNVB3UGlobjVNIiwiYWxnIjoiUFMyNTYifQ.eyJhcHBfaWQiOjQsImNsaWVudF9pZCI6IndlYiIsImF1ZCI6ImZyLmNvcmUuYXBpIiwiaXNzIjoidmludGVkLWlhbS1zZXJ2aWNlIiwic3ViIjoiMjgwNTMzMTQxIiwiaWF0IjoxNzUyOTU4MjM0LCJzaWQiOiIyMTcxNjI3ZC0xNzUyOTU4MjM0Iiwic2NvcGUiOiJ1c2VyIiwiZXhwIjoxNzUzNTYzMDM0LCJwdXJwb3NlIjoicmVmcmVzaCIsImFjdCI6eyJzdWIiOiIyODA1MzMxNDEifSwiYWNjb3VudF9pZCI6MjIxNTA2MTAxfQ.SxJUdeMCNgbpdISUeJwj8cL2b8HGso9GgUe96Q4P4UZoaeP0qvjzs1A3qAXM08BtpXLLfClHjAa4Rs1B8hQbmNtxtQTRN0ceNzqeQ7G9sk0HizPD6btHJ1WmBAktCYZPPk7tkEm8Np4y8Tq2FO68dFGXWT5UB6D4Hur5xalfOkHtsHmdlE0LCxb8jlGICwNRdIzaOkrT_P8h3Rs7_oaKT2FUvkT4L1MF6mpbYZf8Ag-DoYGEsqTfQ8sZZqSqhkrT8n_QovyYeZhZXKzpm-ky3GmmSfya5_vXOrK8t8Q59yiBMmy_Zdf7KQ1uzd3e4tG16pWZaBj0uHyH4NyRtxPEcw"
TEST_USER_ID = "248331973"

async def test_vinted_api():
    """Test direct Vinted API call"""
    
    headers = {
        "x-csrf-token": CSRF_TOKEN,
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    
    url = f"https://www.vinted.co.uk/api/v2/wardrobe/{TEST_USER_ID}/items"
    params = {
        "page": 1,
        "per_page": 20,
        "order": "relevance"
    }
    
    print(f"Testing Vinted API call to: {url}")
    print(f"Headers: {json.dumps({k: v[:50] + '...' if len(v) > 50 else v for k, v in headers.items()}, indent=2)}")
    print(f"Params: {params}")
    print("-" * 80)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Text: {response.text[:500]}...")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"JSON Response Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    if isinstance(data, dict) and 'items' in data:
                        print(f"Number of items: {len(data['items'])}")
                except:
                    print("Failed to parse JSON response")
            
        except Exception as e:
            print(f"Request failed with exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_vinted_api())
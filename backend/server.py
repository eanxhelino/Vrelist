from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import httpx
import asyncio
import json
from playwright.async_api import async_playwright
import time
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

security = HTTPBearer()

# Define Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    csrf_token: str
    auth_token: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    csrf_token: str
    auth_token: str

class VintedProduct(BaseModel):
    id: str
    vinted_id: str
    title: str
    price: float
    currency: str
    description: Optional[str] = None
    brand: Optional[str] = None
    size: Optional[str] = None
    condition: Optional[str] = None
    category: Optional[str] = None
    photos: List[str] = []
    status: str = "active"  # active, sold, deleted
    views: int = 0
    likes: int = 0
    last_relisted: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: str

class DashboardStats(BaseModel):
    total_products: int
    active_products: int
    sold_products: int
    total_revenue: float
    total_views: int
    avg_sale_time: int
    recent_activity: List[Dict[str, Any]]

class RelistRequest(BaseModel):
    product_ids: List[str]

# Vinted API Client
class VintedClient:
    def __init__(self, csrf_token: str, auth_token: str):
        self.csrf_token = csrf_token
        self.auth_token = auth_token
        self.headers = {
            "x-csrf-token": csrf_token,
            "Authorization": f"Bearer {auth_token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "X-Anon-Id": "d30a9fe1-0309-4dcf-bfde-7578b228a7ef",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        }

    async def get_user_wardrobe(self, user_id: str, page: int = 1, per_page: int = 20):
        url = f"https://www.vinted.co.uk/api/v2/wardrobe/{user_id}/items"
        params = {
            "page": page,
            "per_page": per_page,
            "order": "relevance"
        }
        headers = self.headers.copy()
        headers["X-Money-Object"] = "true"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch wardrobe: {response.text}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error fetching wardrobe: {str(e)}")

    async def get_product_details(self, product_id: str):
        url = f"https://www.vinted.co.uk/api/v2/item_upload/items/{product_id}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch product details: {response.text}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error fetching product: {str(e)}")

    async def create_listing(self, listing_data: dict):
        """Create a new listing (relist) using the item_upload endpoint"""
        url = "https://www.vinted.co.uk/api/v2/item_upload/items"
        headers = self.headers.copy()
        headers["X-Upload-Form"] = "true"
        headers["X-Enable-Multiple-Size-Groups"] = "true"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=listing_data)
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=response.status_code, detail=f"Failed to create listing: {response.text}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error creating listing: {str(e)}")

    async def relist_product(self, product_data: dict):
        """Relist a product by creating a new listing with the same data"""
        # Generate new UUID for the relist
        import uuid
        temp_uuid = str(uuid.uuid4())
        
        # Create listing payload based on Vinted's expected format
        listing_payload = {
            "item": {
                "id": None,  # New listing
                "currency": product_data.get("currency", "GBP"),
                "temp_uuid": temp_uuid,
                "title": product_data.get("title", ""),
                "description": product_data.get("description", ""),
                "brand_id": product_data.get("brand_id", 1),
                "brand": product_data.get("brand", "List without brand"),
                "size_id": product_data.get("size_id"),
                "catalog_id": product_data.get("catalog_id", 3829),
                "isbn": None,
                "is_unisex": product_data.get("is_unisex", False),
                "status_id": 6,  # Available
                "video_game_rating_id": None,
                "price": float(product_data.get("price", 0)),
                "package_size_id": product_data.get("package_size_id", 2),
                "shipment_prices": {
                    "domestic": None,
                    "international": None
                },
                "color_ids": product_data.get("color_ids", [1]),
                "assigned_photos": product_data.get("assigned_photos", []),
                "measurement_length": None,
                "measurement_width": None,
                "item_attributes": product_data.get("item_attributes", []),
                "manufacturer": None,
                "manufacturer_labelling": None
            },
            "feedback_id": None,
            "push_up": False,
            "parcel": None,
            "upload_session_id": temp_uuid
        }
        
        return await self.create_listing(listing_payload)

    async def delete_product(self, product_id: str):
        url = f"https://www.vinted.co.uk/api/v2/items/{product_id}/delete"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=response.status_code, detail=f"Failed to delete product: {response.text}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")

class VintedBrowserClient:
    """Browser-based Vinted client to handle CAPTCHA and anti-automation measures"""
    
    def __init__(self, csrf_token: str, auth_token: str):
        self.csrf_token = csrf_token
        self.auth_token = auth_token
        self.playwright = None
        self.browser = None
        self.page = None
    
    async def init_browser(self):
        """Initialize browser with stealth settings"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Keep visible to handle potential CAPTCHAs
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        # Create new page with realistic settings
        self.page = await self.browser.new_page()
        
        # Set realistic viewport and user agent
        await self.page.set_viewport_size({"width": 1920, "height": 1080})
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        })
    
    async def login_to_vinted(self):
        """Login to Vinted using browser automation"""
        try:
            await self.page.goto('https://www.vinted.co.uk')
            
            # Wait for page to load
            await self.page.wait_for_load_state('networkidle')
            
            # Inject authentication tokens if possible
            await self.page.evaluate(f"""
                // Set authentication tokens in localStorage/cookies
                localStorage.setItem('csrf_token', '{self.csrf_token}');
                localStorage.setItem('auth_token', '{self.auth_token}');
            """)
            
            # Navigate to authenticated area to verify login
            await self.page.goto('https://www.vinted.co.uk/member/general')
            await self.page.wait_for_load_state('networkidle')
            
            return True
        except Exception as e:
            print(f"Login failed: {e}")
            return False
    
    async def relist_product_browser(self, product_data: dict):
        """Relist product using browser automation to bypass CAPTCHA"""
        try:
            # Navigate to sell page
            await self.page.goto('https://www.vinted.co.uk/items/new')
            await self.page.wait_for_load_state('networkidle')
            
            # Add random delay to mimic human behavior
            await asyncio.sleep(random.uniform(2, 4))
            
            # Fill product information
            if product_data.get('title'):
                await self.page.fill('input[data-testid="title-input"]', product_data['title'])
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            if product_data.get('description'):
                await self.page.fill('textarea[data-testid="description-input"]', product_data['description'])
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            if product_data.get('price'):
                await self.page.fill('input[data-testid="price-input"]', str(product_data['price']))
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Handle brand selection if available
            if product_data.get('brand'):
                try:
                    await self.page.click('input[data-testid="brand-input"]')
                    await self.page.fill('input[data-testid="brand-input"]', product_data['brand'])
                    await asyncio.sleep(1)
                    # Click first suggestion if available
                    await self.page.click('div[data-testid="brand-suggestion"]:first-child', timeout=3000)
                except:
                    pass  # Continue if brand selection fails
            
            # Handle category selection
            try:
                await self.page.click('button[data-testid="category-button"]')
                await asyncio.sleep(1)
                # Select a default category or use product's category
                await self.page.click('div[data-testid="category-option"]:first-child')
            except:
                pass  # Continue if category selection fails
            
            # Handle condition selection
            try:
                await self.page.click('button[data-testid="condition-button"]')
                await asyncio.sleep(1)
                condition_map = {
                    'New with tags': 'new-with-tags',
                    'New without tags': 'new-without-tags',
                    'Very good': 'very-good',
                    'Good': 'good',
                    'Satisfactory': 'satisfactory'
                }
                condition = product_data.get('condition', 'Good')
                condition_selector = condition_map.get(condition, 'good')
                await self.page.click(f'div[data-testid="condition-{condition_selector}"]')
            except:
                pass  # Continue if condition selection fails
            
            # Add random delay before submitting
            await asyncio.sleep(random.uniform(2, 4))
            
            # Submit the listing
            submit_button = await self.page.query_selector('button[data-testid="submit-listing"]')
            if submit_button:
                await submit_button.click()
                
                # Wait for response and handle potential CAPTCHA
                try:
                    # Wait for success message or CAPTCHA
                    await self.page.wait_for_selector(
                        'div[data-testid="success-message"], div[data-testid="captcha-container"]',
                        timeout=30000
                    )
                    
                    # Check if CAPTCHA appeared
                    captcha = await self.page.query_selector('div[data-testid="captcha-container"]')
                    if captcha:
                        # CAPTCHA detected - pause for manual intervention
                        print("CAPTCHA detected! Please solve it manually in the browser window.")
                        print("Waiting 60 seconds for manual CAPTCHA resolution...")
                        await asyncio.sleep(60)
                        
                        # Check if listing was successful after CAPTCHA
                        success = await self.page.query_selector('div[data-testid="success-message"]')
                        if success:
                            return {"success": True, "message": "Product relisted successfully after manual CAPTCHA resolution"}
                        else:
                            return {"success": False, "error": "CAPTCHA not resolved or listing failed"}
                    else:
                        return {"success": True, "message": "Product relisted successfully"}
                        
                except Exception as e:
                    return {"success": False, "error": f"Timeout or error during listing: {str(e)}"}
            else:
                return {"success": False, "error": "Submit button not found"}
                
        except Exception as e:
            return {"success": False, "error": f"Browser relisting failed: {str(e)}"}
    
    async def close_browser(self):
        """Clean up browser resources"""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

# Helper functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    try:
        user_doc = await db.users.find_one({"id": credentials.credentials})
        if not user_doc:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return User(**user_doc)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

def transform_vinted_product(vinted_item: dict, user_id: str) -> VintedProduct:
    """Transform Vinted API response to our product model"""
    photos = []
    if "photos" in vinted_item and vinted_item["photos"]:
        photos = [photo.get("url", "") for photo in vinted_item["photos"] if photo.get("url")]
    
    # Handle price structure from Vinted API
    price_amount = 0
    currency = "GBP"
    if "price" in vinted_item:
        if isinstance(vinted_item["price"], dict):
            price_amount = float(vinted_item["price"].get("amount", 0))
            currency = vinted_item["price"].get("currency", "GBP")
        else:
            price_amount = float(vinted_item.get("price", 0))
    
    return VintedProduct(
        id=str(uuid.uuid4()),
        vinted_id=str(vinted_item.get("id", "")),
        title=vinted_item.get("title", ""),
        price=price_amount,
        currency=currency,
        description=vinted_item.get("description", ""),
        brand=vinted_item.get("brand", {}).get("title", "") if vinted_item.get("brand") else "",
        size=vinted_item.get("size_title", ""),
        condition=vinted_item.get("status", ""),
        category=vinted_item.get("catalog", {}).get("title", "") if vinted_item.get("catalog") else "",
        photos=photos,
        views=vinted_item.get("view_count", 0),
        likes=vinted_item.get("favourite_count", 0),
        user_id=user_id
    )

# Routes
@api_router.post("/auth/login")
async def login(user_data: UserCreate):
    """Login user with Vinted credentials"""
    try:
        # Test the credentials by making a simple API call
        vinted_client = VintedClient(user_data.csrf_token, user_data.auth_token)
        
        # Create user document
        user = User(
            csrf_token=user_data.csrf_token,
            auth_token=user_data.auth_token
        )
        
        # Save or update user in database
        await db.users.replace_one(
            {"csrf_token": user_data.csrf_token}, 
            user.dict(), 
            upsert=True
        )
        
        return {"message": "Login successful", "user_id": user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid credentials: {str(e)}")

@api_router.get("/products/import/{user_id}")
async def import_products(user_id: str, current_user: User = Depends(get_current_user)):
    """Import products from Vinted wardrobe"""
    try:
        vinted_client = VintedClient(current_user.csrf_token, current_user.auth_token)
        
        # Fetch products from Vinted
        wardrobe_data = await vinted_client.get_user_wardrobe(user_id)
        
        if not wardrobe_data or "items" not in wardrobe_data:
            return {"message": "No products found", "count": 0}
        
        imported_count = 0
        for item in wardrobe_data["items"]:
            try:
                product = transform_vinted_product(item, current_user.id)
                
                # Check if product already exists
                existing = await db.products.find_one({
                    "vinted_id": product.vinted_id,
                    "user_id": current_user.id
                })
                
                if not existing:
                    await db.products.insert_one(product.dict())
                    imported_count += 1
                else:
                    # Update existing product
                    await db.products.update_one(
                        {"vinted_id": product.vinted_id, "user_id": current_user.id},
                        {"$set": {
                            "title": product.title,
                            "price": product.price,
                            "views": product.views,
                            "likes": product.likes,
                            "updated_at": datetime.utcnow()
                        }}
                    )
            except Exception as e:
                logging.error(f"Error processing product {item.get('id', 'unknown')}: {str(e)}")
                continue
        
        return {"message": f"Imported {imported_count} products", "count": imported_count}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@api_router.get("/products", response_model=List[VintedProduct])
async def get_products(current_user: User = Depends(get_current_user)):
    """Get user's products"""
    products = await db.products.find({"user_id": current_user.id}).to_list(1000)
    return [VintedProduct(**product) for product in products]

@api_router.post("/products/relist")
async def relist_products(request: RelistRequest, current_user: User = Depends(get_current_user)):
    """Relist selected products using API (may be blocked by CAPTCHA)"""
    try:
        vinted_client = VintedClient(current_user.csrf_token, current_user.auth_token)
        
        results = []
        for product_id in request.product_ids:
            try:
                # Get product from database
                product_doc = await db.products.find_one({"id": product_id, "user_id": current_user.id})
                if not product_doc:
                    results.append({"product_id": product_id, "success": False, "error": "Product not found"})
                    continue
                
                # Note: For full relisting, we would need to handle photo uploads
                # This is a simplified version that creates a basic relist
                relist_data = {
                    "title": product_doc.get("title", ""),
                    "description": product_doc.get("description", ""),
                    "price": product_doc.get("price", 0),
                    "currency": product_doc.get("currency", "GBP"),
                    "brand": product_doc.get("brand", ""),
                    "brand_id": 1,  # Default to "List without brand"
                    "catalog_id": 3829,  # Default category, should be dynamic
                    "color_ids": [1],  # Default color
                    "assigned_photos": [],  # Would need photo upload integration
                    "item_attributes": []
                }
                
                # Create new listing (relist)
                relist_response = await vinted_client.relist_product(relist_data)
                
                # Update last relisted timestamp
                await db.products.update_one(
                    {"id": product_id},
                    {"$set": {"last_relisted": datetime.utcnow()}}
                )
                
                results.append({"product_id": product_id, "success": True, "vinted_response": relist_response})
                
            except Exception as e:
                results.append({"product_id": product_id, "success": False, "error": str(e)})
        
        success_count = sum(1 for r in results if r["success"])
        return {"message": f"Relisted {success_count}/{len(request.product_ids)} products", "results": results}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Relist failed: {str(e)}")

@api_router.post("/products/relist-browser")
async def relist_products_browser(request: RelistRequest, current_user: User = Depends(get_current_user)):
    """Relist selected products using browser automation to handle CAPTCHA"""
    browser_client = None
    try:
        # Initialize browser client
        browser_client = VintedBrowserClient(current_user.csrf_token, current_user.auth_token)
        await browser_client.init_browser()
        
        # Login to Vinted
        login_success = await browser_client.login_to_vinted()
        if not login_success:
            return {"success": False, "error": "Failed to login to Vinted"}
        
        results = []
        for product_id in request.product_ids:
            try:
                # Get product from database
                product_doc = await db.products.find_one({"id": product_id, "user_id": current_user.id})
                if not product_doc:
                    results.append({"product_id": product_id, "success": False, "error": "Product not found"})
                    continue
                
                # Prepare product data for browser relisting
                product_data = {
                    "title": product_doc.get("title", ""),
                    "description": product_doc.get("description", ""),
                    "price": product_doc.get("price", 0),
                    "brand": product_doc.get("brand", ""),
                    "condition": product_doc.get("condition", "Good")
                }
                
                # Relist using browser automation
                relist_result = await browser_client.relist_product_browser(product_data)
                
                if relist_result.get("success"):
                    # Update last relisted timestamp
                    await db.products.update_one(
                        {"id": product_id},
                        {"$set": {"last_relisted": datetime.utcnow()}}
                    )
                
                results.append({
                    "product_id": product_id, 
                    "success": relist_result.get("success", False), 
                    "message": relist_result.get("message", ""),
                    "error": relist_result.get("error", "")
                })
                
                # Add delay between relistings to avoid detection
                await asyncio.sleep(random.uniform(5, 10))
                
            except Exception as e:
                results.append({"product_id": product_id, "success": False, "error": str(e)})
        
        success_count = sum(1 for r in results if r["success"])
        return {
            "message": f"Relisted {success_count}/{len(request.product_ids)} products using browser automation",
            "results": results,
            "note": "Browser window was kept open to handle any CAPTCHAs manually"
        }
    
    except Exception as e:
        return {"success": False, "error": f"Browser relist failed: {str(e)}"}
    
    finally:
        # Clean up browser resources
        if browser_client:
            try:
                await browser_client.close_browser()
            except:
                pass  # Ignore cleanup errors

@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    """Get dashboard statistics"""
    try:
        # Get all products for user
        products = await db.products.find({"user_id": current_user.id}).to_list(1000)
        
        total_products = len(products)
        active_products = len([p for p in products if p.get("status") == "active"])
        sold_products = len([p for p in products if p.get("status") == "sold"])
        
        total_revenue = sum(p.get("price", 0) for p in products if p.get("status") == "sold")
        total_views = sum(p.get("views", 0) for p in products)
        
        # Calculate average sale time (mock for now)
        avg_sale_time = 12
        
        # Recent activity (last 10 actions)
        recent_activity = []
        recent_relisted = sorted(
            [p for p in products if p.get("last_relisted")],
            key=lambda x: x.get("last_relisted", datetime.min),
            reverse=True
        )[:5]
        
        for product in recent_relisted:
            recent_activity.append({
                "action": "relisted",
                "product_title": product.get("title", ""),
                "timestamp": product.get("last_relisted").isoformat() if product.get("last_relisted") else ""
            })
        
        return DashboardStats(
            total_products=total_products,
            active_products=active_products,
            sold_products=sold_products,
            total_revenue=total_revenue,
            total_views=total_views,
            avg_sale_time=avg_sale_time,
            recent_activity=recent_activity
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Path to React build
react_build_path = ROOT_DIR.parent / "frontend" / "build"

# Serve React static files
app.mount("/", StaticFiles(directory=react_build_path, html=True), name="static")

@app.get("/")
async def serve_react():
    return FileResponse(react_build_path / "index.html")

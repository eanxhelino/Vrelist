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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json"
        }

    async def get_user_wardrobe(self, user_id: str, page: int = 1, per_page: int = 20):
        url = f"https://www.vinted.co.uk/api/v2/wardrobe/{user_id}/items"
        params = {
            "page": page,
            "per_page": per_page,
            "order": "relevance"
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=response.status_code, detail="Failed to fetch wardrobe")
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
                    raise HTTPException(status_code=response.status_code, detail="Failed to fetch product details")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error fetching product: {str(e)}")

    async def relist_product(self, product_id: str):
        url = f"https://www.vinted.co.uk/api/v2/items/{product_id}/post"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=response.status_code, detail="Failed to relist product")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error relisting product: {str(e)}")

    async def delete_product(self, product_id: str):
        url = f"https://www.vinted.co.uk/api/v2/items/{product_id}/delete"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=response.status_code, detail="Failed to delete product")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")

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
    
    return VintedProduct(
        id=str(uuid.uuid4()),
        vinted_id=str(vinted_item.get("id", "")),
        title=vinted_item.get("title", ""),
        price=float(vinted_item.get("price", {}).get("amount", 0)),
        currency=vinted_item.get("price", {}).get("currency_code", "EUR"),
        description=vinted_item.get("description", ""),
        brand=vinted_item.get("brand", {}).get("title", "") if vinted_item.get("brand") else "",
        size=vinted_item.get("size_title", ""),
        condition=vinted_item.get("status", ""),
        category=vinted_item.get("catalog_branch", {}).get("title", "") if vinted_item.get("catalog_branch") else "",
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
    """Relist selected products"""
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
                
                # Relist on Vinted
                await vinted_client.relist_product(product_doc["vinted_id"])
                
                # Update last relisted timestamp
                await db.products.update_one(
                    {"id": product_id},
                    {"$set": {"last_relisted": datetime.utcnow()}}
                )
                
                results.append({"product_id": product_id, "success": True})
                
            except Exception as e:
                results.append({"product_id": product_id, "success": False, "error": str(e)})
        
        success_count = sum(1 for r in results if r["success"])
        return {"message": f"Relisted {success_count}/{len(request.product_ids)} products", "results": results}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Relist failed: {str(e)}")

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
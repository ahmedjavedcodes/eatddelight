from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router)

# Later plans append: settings, categories, menu, foods, cart, favourites,
# orders, contact, and the admin.* routers.

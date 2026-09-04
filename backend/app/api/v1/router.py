from fastapi import APIRouter

from app.api.v1.admin import addons as admin_addons
from app.api.v1.admin import auth as admin_auth
from app.api.v1.admin import categories as admin_categories
from app.api.v1.admin import contact_messages as admin_contact_messages
from app.api.v1.admin import foods as admin_foods
from app.api.v1.admin import orders as admin_orders
from app.api.v1.admin import settings as admin_settings
from app.api.v1.admin import staff as admin_staff
from app.api.v1.endpoints import categories, contact, foods, health, menu, settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(settings.router)
api_router.include_router(categories.router)
api_router.include_router(menu.router)
api_router.include_router(foods.router)
api_router.include_router(contact.router)

api_router.include_router(admin_auth.router)
api_router.include_router(admin_categories.router)
api_router.include_router(admin_foods.router)
api_router.include_router(admin_addons.router)
api_router.include_router(admin_orders.router)
api_router.include_router(admin_staff.router)
api_router.include_router(admin_settings.router)
api_router.include_router(admin_contact_messages.router)

# Cart and favourites are handled client-side in the Next.js frontend; not built here.
# Order placement / checkout / invoice PDF remain out of scope until requested.

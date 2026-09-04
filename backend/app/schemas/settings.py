from pydantic import BaseModel, ConfigDict


class SiteSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_name: str
    tagline: str | None
    about_text: str | None
    contact_phone: str
    whatsapp_number: str
    instagram_handle: str
    address: str | None
    opening_hours: str | None

from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Optional


class FoodRecordCreate(BaseModel):
    dish_name: str = Field(..., min_length=1, max_length=200)
    restaurant: str = Field(..., min_length=1, max_length=200)
    cuisine_tag: str = Field(..., min_length=1, max_length=50)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    location_name: str = ""
    rating: int = Field(..., ge=1, le=5)
    date_eaten: str = ""  # YYYY-MM-DD, 前端默认当天，后端可接受空字符串
    comment: str = ""


class FoodRecordOut(FoodRecordCreate):
    id: int
    photo_path: str = ""
    thumbnail_path: str = ""
    created_at: str = ""
    updated_at: str = ""

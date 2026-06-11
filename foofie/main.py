import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import (
    init_db, get_all_records, get_records_by_restaurant,
    get_record_by_id, search_records, insert_record,
    update_record, delete_record, get_cuisine_tags, get_records_json,
)
from photo_utils import validate_photo, save_photo, delete_photo

app = FastAPI(title="Foofie")

# 挂载静态文件
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(BASE_DIR / "uploads")), name="uploads")
app.mount("/thumbnails", StaticFiles(directory=str(BASE_DIR / "thumbnails")), name="thumbnails")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def index(request: Request, view: str = "dish", q: str = "", tag: str = ""):
    tags = get_cuisine_tags()

    if view == "restaurant":
        groups = get_records_by_restaurant()
        # 如果有搜索条件，在内存中过滤
        if q:
            q_lower = q.lower()
            filtered = []
            for g in groups:
                matched_records = [
                    r for r in g["records"]
                    if q_lower in r["dish_name"].lower()
                    or q_lower in r["restaurant"].lower()
                    or q_lower in r["cuisine_tag"].lower()
                ]
                if matched_records:
                    g["records"] = matched_records
                    g["count"] = len(matched_records)
                    filtered.append(g)
            groups = filtered
        if tag:
            filtered = []
            for g in groups:
                matched_records = [r for r in g["records"] if r["cuisine_tag"] == tag]
                if matched_records:
                    g["records"] = matched_records
                    g["count"] = len(matched_records)
                    filtered.append(g)
            groups = filtered
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "view": view, "groups": groups, "tags": tags, "q": q, "active_tag": tag},
        )

    # 菜品模式
    if q:
        records = search_records(q)
    elif tag:
        records = [r for r in get_all_records() if r["cuisine_tag"] == tag]
    else:
        records = get_all_records()

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "view": "dish", "records": records, "tags": tags, "q": q, "active_tag": tag},
    )


@app.get("/add")
def add_form(request: Request):
    tags = get_cuisine_tags()
    today = date.today().isoformat()
    return templates.TemplateResponse(
        "add.html",
        {"request": request, "record": None, "tags": tags, "today": today},
    )


@app.post("/add")
async def add_submit(
    request: Request,
    dish_name: str = Form(...),
    restaurant: str = Form(...),
    cuisine_tag: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    location_name: str = Form(""),
    rating: int = Form(...),
    date_eaten: str = Form(...),
    comment: str = Form(""),
    photo: UploadFile | None = File(None),
):
    # 验证经纬度
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise HTTPException(400, "经纬度超出有效范围")
    if not (1 <= rating <= 5):
        raise HTTPException(400, "评分必须在 1-5 之间")

    photo_path = ""
    thumbnail_path = ""
    if photo and photo.filename:
        valid, err = validate_photo(photo)
        if not valid:
            raise HTTPException(400, err)
        photo_path, thumbnail_path = await save_photo(photo)

    record_id = insert_record(
        dish_name=dish_name,
        restaurant=restaurant,
        cuisine_tag=cuisine_tag,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        rating=rating,
        date_eaten=date_eaten,
        comment=comment,
        photo_path=photo_path,
        thumbnail_path=thumbnail_path,
    )
    return RedirectResponse(url=f"/record/{record_id}", status_code=303)


@app.get("/record/{record_id}")
def detail(request: Request, record_id: int):
    record = get_record_by_id(record_id)
    if not record:
        raise HTTPException(404, "记录不存在")
    return templates.TemplateResponse(
        "detail.html",
        {"request": request, "record": record},
    )


@app.get("/record/{record_id}/edit")
def edit_form(request: Request, record_id: int):
    record = get_record_by_id(record_id)
    if not record:
        raise HTTPException(404, "记录不存在")
    tags = get_cuisine_tags()
    return templates.TemplateResponse(
        "add.html",
        {"request": request, "record": record, "tags": tags, "today": date.today().isoformat()},
    )


@app.post("/record/{record_id}/edit")
async def edit_submit(
    request: Request,
    record_id: int,
    dish_name: str = Form(...),
    restaurant: str = Form(...),
    cuisine_tag: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    location_name: str = Form(""),
    rating: int = Form(...),
    date_eaten: str = Form(...),
    comment: str = Form(""),
    photo: UploadFile | None = File(None),
):
    existing = get_record_by_id(record_id)
    if not existing:
        raise HTTPException(404, "记录不存在")

    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise HTTPException(400, "经纬度超出有效范围")
    if not (1 <= rating <= 5):
        raise HTTPException(400, "评分必须在 1-5 之间")

    photo_path = existing["photo_path"]
    thumbnail_path = existing["thumbnail_path"]

    if photo and photo.filename:
        valid, err = validate_photo(photo)
        if not valid:
            raise HTTPException(400, err)
        # 删除旧照片
        delete_photo(photo_path, thumbnail_path)
        photo_path, thumbnail_path = await save_photo(photo)

    update_record(
        record_id=record_id,
        dish_name=dish_name,
        restaurant=restaurant,
        cuisine_tag=cuisine_tag,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        rating=rating,
        date_eaten=date_eaten,
        comment=comment,
        photo_path=photo_path,
        thumbnail_path=thumbnail_path,
    )
    return RedirectResponse(url=f"/record/{record_id}", status_code=303)


@app.post("/record/{record_id}/delete")
def delete(record_id: int):
    record = get_record_by_id(record_id)
    if not record:
        raise HTTPException(404, "记录不存在")
    delete_photo(record["photo_path"], record["thumbnail_path"])
    delete_record(record_id)
    return RedirectResponse(url="/", status_code=303)


@app.get("/globe")
def globe(request: Request):
    return templates.TemplateResponse("globe.html", {"request": request})


@app.get("/api/records")
def api_records():
    return get_records_json()

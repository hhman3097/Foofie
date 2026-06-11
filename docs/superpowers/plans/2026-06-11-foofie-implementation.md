# Foofie 美食记录应用 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个可本地运行的美食记录 Web 应用，支持菜品增删改查、3D 地球可视化和响应式适配。

**Architecture:** FastAPI + Jinja2 模板渲染 + SQLite 数据库。前端使用 Tailwind CSS (CDN) 做响应式布局，Three.js (CDN) 渲染 3D 地球。照片上传后自动生成缩略图，列表和地球视图使用缩略图提升性能。

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, SQLite3, Jinja2, Tailwind CSS, Three.js, Pillow (缩略图)

---

## 文件结构

```
/home/frank/cc/foofie/                    # 项目根目录
├── main.py                               # FastAPI 入口 + 所有路由
├── database.py                           # SQLite 初始化 + 数据库操作函数
├── models.py                             # Pydantic 数据模型
├── photo_utils.py                        # 照片保存 + 缩略图生成
├── requirements.txt                      # Python 依赖
├── templates/
│   ├── base.html                         # 基础布局（响应式导航栏）
│   ├── index.html                        # 列表页（菜品模式 + 餐厅模式）
│   ├── add.html                          # 添加/编辑表单
│   ├── detail.html                       # 菜品详情页
│   └── globe.html                        # 3D 地球视图
├── static/
│   └── css/
│       └── style.css                     # 自定义样式
├── uploads/                              # 上传的原图（.gitkeep）
├── thumbnails/                           # 缩略图（.gitkeep）
└── foofie.db                             # SQLite 数据库（运行时自动生成）
```

---

### Task 1: 项目脚手架 + 数据库层

**文件:**
- Create: `foofie/requirements.txt`
- Create: `foofie/database.py`
- Create: `foofie/models.py`

- [ ] **Step 1: 创建项目目录结构和 requirements.txt**

```bash
mkdir -p /home/frank/cc/foofie/{templates,static/css,uploads,thumbnails}
touch /home/frank/cc/foofie/uploads/.gitkeep
touch /home/frank/cc/foofie/thumbnails/.gitkeep
```

`foofie/requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.17
Pillow==11.0.0
aiofiles==24.1.0
```

- [ ] **Step 2: 编写数据模型 models.py**

`foofie/models.py`:
```python
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
    date_eaten: str = ""  # YYYY-MM-DD, 默认为当天
    comment: str = ""


class FoodRecordOut(FoodRecordCreate):
    id: int
    photo_path: str = ""
    thumbnail_path: str = ""
    created_at: str = ""
    updated_at: str = ""
```

- [ ] **Step 3: 编写数据库层 database.py**

`foofie/database.py`:
```python
import sqlite3
import os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "foofie.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS food_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dish_name TEXT NOT NULL,
            restaurant TEXT NOT NULL,
            cuisine_tag TEXT NOT NULL,
            latitude REAL NOT NULL CHECK(latitude >= -90 AND latitude <= 90),
            longitude REAL NOT NULL CHECK(longitude >= -180 AND longitude <= 180),
            location_name TEXT DEFAULT '',
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            date_eaten TEXT NOT NULL,
            comment TEXT DEFAULT '',
            photo_path TEXT DEFAULT '',
            thumbnail_path TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_date ON food_records(date_eaten DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_restaurant ON food_records(restaurant)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_tag ON food_records(cuisine_tag)")
    conn.commit()
    conn.close()


def get_all_records(order_by: str = "date_eaten DESC") -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(f"SELECT * FROM food_records ORDER BY {order_by}").fetchall()
    conn.close()
    return rows


def get_records_by_restaurant() -> list[dict]:
    """返回按餐厅分组的数据，每组包含餐厅信息和菜品列表"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM food_records ORDER BY restaurant, date_eaten DESC"
    ).fetchall()
    conn.close()

    groups: dict[str, dict] = {}
    for row in rows:
        r = row["restaurant"]
        if r not in groups:
            groups[r] = {"restaurant": r, "count": 0, "total_rating": 0, "records": []}
        groups[r]["count"] += 1
        groups[r]["total_rating"] += row["rating"]
        groups[r]["records"].append(dict(row))

    result = []
    for r_name, data in groups.items():
        avg = round(data["total_rating"] / data["count"], 1)
        result.append({
            "restaurant": r_name,
            "count": data["count"],
            "avg_rating": avg,
            "records": data["records"],
        })
    # 按菜品数量降序排列
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


def get_record_by_id(record_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM food_records WHERE id = ?", (record_id,)).fetchone()
    conn.close()
    return row


def search_records(q: str) -> list[sqlite3.Row]:
    pattern = f"%{q}%"
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM food_records WHERE dish_name LIKE ? OR restaurant LIKE ? OR cuisine_tag LIKE ? ORDER BY date_eaten DESC",
        (pattern, pattern, pattern),
    ).fetchall()
    conn.close()
    return rows


def insert_record(
    dish_name: str,
    restaurant: str,
    cuisine_tag: str,
    latitude: float,
    longitude: float,
    rating: int,
    date_eaten: str,
    comment: str = "",
    location_name: str = "",
    photo_path: str = "",
    thumbnail_path: str = "",
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO food_records
           (dish_name, restaurant, cuisine_tag, latitude, longitude,
            location_name, rating, date_eaten, comment, photo_path, thumbnail_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (dish_name, restaurant, cuisine_tag, latitude, longitude,
         location_name, rating, date_eaten, comment, photo_path, thumbnail_path),
    )
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return record_id


def update_record(
    record_id: int,
    dish_name: str,
    restaurant: str,
    cuisine_tag: str,
    latitude: float,
    longitude: float,
    rating: int,
    date_eaten: str,
    comment: str = "",
    location_name: str = "",
    photo_path: str = "",
    thumbnail_path: str = "",
):
    conn = get_connection()
    conn.execute(
        """UPDATE food_records SET
           dish_name=?, restaurant=?, cuisine_tag=?, latitude=?, longitude=?,
           location_name=?, rating=?, date_eaten=?, comment=?, photo_path=?,
           thumbnail_path=?, updated_at=datetime('now', 'localtime')
           WHERE id=?""",
        (dish_name, restaurant, cuisine_tag, latitude, longitude,
         location_name, rating, date_eaten, comment, photo_path,
         thumbnail_path, record_id),
    )
    conn.commit()
    conn.close()


def delete_record(record_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM food_records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def get_cuisine_tags() -> list[str]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT cuisine_tag FROM food_records ORDER BY cuisine_tag"
    ).fetchall()
    conn.close()
    return [r["cuisine_tag"] for r in rows]


def get_records_json() -> list[dict]:
    """返回用于 3D 地球的 JSON 数据"""
    rows = get_all_records()
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "dish_name": r["dish_name"],
            "restaurant": r["restaurant"],
            "cuisine_tag": r["cuisine_tag"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "location_name": r["location_name"],
            "rating": r["rating"],
            "date_eaten": r["date_eaten"],
            "thumbnail_path": f"/thumbnails/{r['thumbnail_path']}" if r["thumbnail_path"] else "",
        })
    return result
```

- [ ] **Step 4: 初始化数据库并提交**

```bash
cd /home/frank/cc
python3 -c "
from foofie.database import init_db
init_db()
print('Database initialized successfully')
"
```

```bash
cd /home/frank/cc
git init
git add foofie/requirements.txt foofie/database.py foofie/models.py foofie/uploads/.gitkeep foofie/thumbnails/.gitkeep
git commit -m "feat: project scaffolding and database layer"
```

---

### Task 2: 照片处理工具

**文件:**
- Create: `foofie/photo_utils.py`

- [ ] **Step 1: 编写 photo_utils.py**

`foofie/photo_utils.py`:
```python
import os
import uuid
from PIL import Image
from fastapi import UploadFile

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
THUMBNAIL_SIZE = (300, 300)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
THUMBNAIL_DIR = os.path.join(BASE_DIR, "thumbnails")


def validate_photo(file: UploadFile) -> tuple[bool, str]:
    """验证照片格式和大小，返回 (是否合法, 错误信息)"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"不支持的文件格式: {ext}，仅支持 jpg/png/webp"
    if file.content_type not in ALLOWED_MIME_TYPES:
        return False, f"不支持的 MIME 类型: {file.content_type}"
    return True, ""


async def save_photo(file: UploadFile) -> tuple[str, str]:
    """保存照片并生成缩略图，返回 (photo_filename, thumbnail_filename)"""
    ext = os.path.splitext(file.filename or "photo.jpg")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError(f"文件过大，超过 5MB 限制")

    with open(filepath, "wb") as f:
        f.write(contents)

    # 生成缩略图
    thumb_filename = f"{uuid.uuid4().hex}{ext}"
    thumb_path = os.path.join(THUMBNAIL_DIR, thumb_filename)
    try:
        img = Image.open(filepath)
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        img.save(thumb_path)
    except Exception as e:
        # 缩略图生成失败不影响原图保存
        print(f"Thumbnail generation failed: {e}")
        thumb_filename = ""

    return filename, thumb_filename


def delete_photo(photo_path: str, thumbnail_path: str):
    """删除照片和缩略图文件"""
    if photo_path:
        p = os.path.join(UPLOAD_DIR, photo_path)
        if os.path.exists(p):
            os.remove(p)
    if thumbnail_path:
        p = os.path.join(THUMBNAIL_DIR, thumbnail_path)
        if os.path.exists(p):
            os.remove(p)
```

- [ ] **Step 2: 提交**

```bash
cd /home/frank/cc
git add foofie/photo_utils.py
git commit -m "feat: photo upload and thumbnail generation"
```

---

### Task 3: FastAPI 主应用 — 路由

**文件:**
- Create: `foofie/main.py`

- [ ] **Step 1: 编写 main.py（包含所有路由）**

`foofie/main.py`:
```python
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
```

- [ ] **Step 2: 提交**

```bash
cd /home/frank/cc
git add foofie/main.py
git commit -m "feat: FastAPI app with all routes"
```

---

### Task 4: 基础模板 + 自定义样式

**文件:**
- Create: `foofie/templates/base.html`
- Modify: `foofie/static/css/style.css`

- [ ] **Step 1: 编写 base.html（响应式布局）**

`foofie/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Foofie 🍜{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="/static/css/style.css">
    {% block head_extra %}{% endblock %}
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- 顶部导航 -->
    <nav class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-40">
        <div class="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
            <a href="/" class="text-xl font-bold text-orange-500 hover:text-orange-600">
                Foofie 🍜
            </a>
            <div class="flex items-center gap-2">
                {% if request.url.path == "/" %}
                <a href="/globe" class="px-3 py-1.5 text-sm bg-green-100 text-green-700 rounded-full hover:bg-green-200 transition">
                    🌍 地球
                </a>
                {% endif %}
                {% if request.url.path != "/" and request.url.path != "/add" %}
                <a href="/" class="px-3 py-1.5 text-sm bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200 transition">
                    ← 返回
                </a>
                {% endif %}
            </div>
        </div>
    </nav>

    <!-- 主内容 -->
    <main class="max-w-4xl mx-auto px-4 py-6">
        {% block content %}{% endblock %}
    </main>

    <!-- 浮动添加按钮（仅在首页显示） -->
    {% if request.url.path == "/" %}
    <a href="/add"
       class="fixed bottom-6 right-6 w-14 h-14 bg-orange-500 text-white rounded-full shadow-lg
              flex items-center justify-center text-3xl hover:bg-orange-600 hover:shadow-xl
              transition-all active:scale-95 z-50">
        +
    </a>
    {% endif %}
</body>
</html>
```

- [ ] **Step 2: 编写自定义样式**

`foofie/static/css/style.css`:
```css
/* 星星评分 */
.star-rating input {
    display: none;
}
.star-rating label {
    font-size: 1.5rem;
    color: #ddd;
    cursor: pointer;
    transition: color 0.15s;
}
.star-rating label:hover,
.star-rating label:hover ~ label,
.star-rating input:checked ~ label {
    color: #f59e0b;
}
.star-rating {
    direction: rtl;
    display: inline-flex;
    gap: 2px;
}

/* 卡片悬停效果 */
.record-card {
    transition: transform 0.15s, box-shadow 0.15s;
}
.record-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

/* 标签气泡 */
.tag-badge {
    @apply inline-block px-2.5 py-0.5 rounded-full text-xs font-medium;
}

/* 3D 地球全屏 */
.globe-container {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 10;
}

/* 移动端适配 */
@media (max-width: 767px) {
    .star-rating label {
        font-size: 1.8rem; /* 移动端点击区域更大 */
    }
    .record-card {
        margin-bottom: 0.75rem;
    }
}
```

- [ ] **Step 3: 提交**

```bash
cd /home/frank/cc
git add foofie/templates/base.html foofie/static/css/style.css
git commit -m "feat: base template with responsive layout and custom styles"
```

---

### Task 5: 首页 — 列表视图（菜品模式 + 餐厅模式）

**文件:**
- Create: `foofie/templates/index.html`

- [ ] **Step 1: 编写 index.html**

`foofie/templates/index.html`:
```html
{% extends "base.html" %}
{% block title %}Foofie 🍜 — 美食记录{% endblock %}

{% block content %}
<!-- 搜索和筛选栏 -->
<div class="mb-6 space-y-3">
    <!-- 模式切换 + 搜索 -->
    <div class="flex items-center gap-2">
        <div class="flex bg-gray-100 rounded-full p-0.5 text-sm">
            <a href="/?view=dish{% if q %}&q={{ q }}{% endif %}{% if active_tag %}&tag={{ active_tag }}{% endif %}"
               class="px-4 py-1.5 rounded-full transition {% if view == 'dish' %}bg-white shadow-sm font-medium{% else %}text-gray-500 hover:text-gray-700{% endif %}">
                🍽️ 菜品
            </a>
            <a href="/?view=restaurant{% if q %}&q={{ q }}{% endif %}{% if active_tag %}&tag={{ active_tag }}{% endif %}"
               class="px-4 py-1.5 rounded-full transition {% if view == 'restaurant' %}bg-white shadow-sm font-medium{% else %}text-gray-500 hover:text-gray-700{% endif %}">
                🏪 餐厅
            </a>
        </div>
    </div>

    <!-- 搜索 -->
    <form method="get" class="flex gap-2">
        {% if view %}<input type="hidden" name="view" value="{{ view }}">{% endif %}
        <input type="text" name="q" value="{{ q }}" placeholder="搜索菜名、餐厅、标签..."
               class="flex-1 px-4 py-2 border border-gray-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent">
        <button type="submit" class="px-4 py-2 bg-orange-500 text-white rounded-full text-sm hover:bg-orange-600 transition">搜索</button>
    </form>

    <!-- 标签筛选 -->
    {% if tags %}
    <div class="flex gap-1.5 flex-wrap">
        {% if active_tag %}
        <a href="/?view={{ view }}{% if q %}&q={{ q }}{% endif %}" class="tag-badge bg-gray-200 text-gray-600 hover:bg-gray-300">✕ 清除</a>
        {% endif %}
        {% for tag in tags %}
        <a href="/?view={{ view }}&tag={{ tag }}{% if q %}&q={{ q }}{% endif %}"
           class="tag-badge {% if active_tag == tag %}bg-orange-500 text-white{% else %}bg-orange-100 text-orange-700 hover:bg-orange-200{% endif %}">
            {{ tag }}
        </a>
        {% endfor %}
    </div>
    {% endif %}
</div>

<!-- 菜品模式 -->
{% if view == "dish" %}
    {% if records %}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {% for r in records %}
        <a href="/record/{{ r.id }}" class="record-card block bg-white rounded-xl border border-gray-100 overflow-hidden shadow-sm">
            {% if r.thumbnail_path %}
            <div class="aspect-video bg-gray-100 overflow-hidden">
                <img src="/thumbnails/{{ r.thumbnail_path }}" alt="{{ r.dish_name }}" class="w-full h-full object-cover">
            </div>
            {% endif %}
            <div class="p-4 space-y-1.5">
                <h3 class="font-bold text-lg text-gray-900">{{ r.dish_name }}</h3>
                <p class="text-sm text-gray-500">🏪 {{ r.restaurant }}</p>
                <div class="flex items-center justify-between">
                    <span class="tag-badge bg-orange-100 text-orange-700">{{ r.cuisine_tag }}</span>
                    <span class="text-amber-400 text-sm">
                        {% for i in range(r.rating) %}⭐{% endfor %}
                    </span>
                </div>
                {% if r.location_name %}
                <p class="text-xs text-gray-400">📍 {{ r.location_name }}</p>
                {% endif %}
                <p class="text-xs text-gray-300">{{ r.date_eaten }}</p>
            </div>
        </a>
        {% endfor %}
    </div>
    {% else %}
    <div class="text-center py-16 text-gray-400">
        <p class="text-5xl mb-4">🍜</p>
        <p class="text-lg">还没有记录</p>
        <p class="text-sm mt-1">点击右下角 + 添加你的第一条美食记录吧</p>
    </div>
    {% endif %}

<!-- 餐厅模式 -->
{% elif view == "restaurant" %}
    {% if groups %}
    <div class="space-y-4">
        {% for g in groups %}
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <details class="group" {% if loop.first %}open{% endif %}>
                <summary class="p-4 cursor-pointer hover:bg-gray-50 transition flex items-center justify-between">
                    <div>
                        <h3 class="font-bold text-lg text-gray-900">🏪 {{ g.restaurant }}</h3>
                        <p class="text-sm text-gray-400">
                            {{ g.count }} 道菜 · ⭐ {{ g.avg_rating }}
                        </p>
                    </div>
                    <span class="text-gray-300 group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div class="px-4 pb-4 space-y-3">
                    {% for r in g.records %}
                    <a href="/record/{{ r.id }}" class="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition">
                        {% if r.thumbnail_path %}
                        <div class="w-14 h-14 rounded-lg bg-gray-100 overflow-hidden flex-shrink-0">
                            <img src="/thumbnails/{{ r.thumbnail_path }}" alt="" class="w-full h-full object-cover">
                        </div>
                        {% else %}
                        <div class="w-14 h-14 rounded-lg bg-gray-100 flex items-center justify-center text-2xl flex-shrink-0">
                            🍽️
                        </div>
                        {% endif %}
                        <div class="flex-1 min-w-0">
                            <p class="font-medium text-gray-900 truncate">{{ r.dish_name }}</p>
                            <div class="flex items-center gap-2 text-sm">
                                <span class="tag-badge bg-orange-100 text-orange-700">{{ r.cuisine_tag }}</span>
                                <span class="text-amber-400 text-xs">
                                    {% for i in range(r.rating) %}⭐{% endfor %}
                                </span>
                            </div>
                        </div>
                        <span class="text-xs text-gray-300">{{ r.date_eaten }}</span>
                    </a>
                    {% endfor %}
                </div>
            </details>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="text-center py-16 text-gray-400">
        <p class="text-5xl mb-4">🏪</p>
        <p class="text-lg">还没有餐厅记录</p>
    </div>
    {% endif %}
{% endif %}
{% endblock %}
```

- [ ] **Step 2: 提交**

```bash
cd /home/frank/cc
git add foofie/templates/index.html
git commit -m "feat: index page with dish and restaurant mode"
```

---

### Task 6: 添加/编辑表单页面

**文件:**
- Create: `foofie/templates/add.html`

- [ ] **Step 1: 编写 add.html（同时用于添加和编辑）**

`foofie/templates/add.html`:
```html
{% extends "base.html" %}
{% block title %}{% if record %}编辑{% else %}添加{% endif %} 美食记录{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">
        {% if record %}✏️ 编辑{% else %}✨ 添加{% endif %}美食记录
    </h1>

    <form method="post" enctype="multipart/form-data"
          action="{% if record %}/record/{{ record.id }}/edit{% else %}/add{% endif %}"
          class="space-y-5" onsubmit="return validateForm()">

        <!-- 菜名 -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">🍽️ 菜名 *</label>
            <input type="text" name="dish_name" required maxlength="200"
                   value="{{ record.dish_name if record else '' }}"
                   class="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-300">
        </div>

        <!-- 餐厅名 -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">🏪 餐厅名 *</label>
            <input type="text" name="restaurant" required maxlength="200"
                   value="{{ record.restaurant if record else '' }}"
                   class="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-300">
        </div>

        <!-- 标签 -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">🏷️ 菜系/标签 *</label>
            <input type="text" name="cuisine_tag" required list="tag-list" maxlength="50"
                   value="{{ record.cuisine_tag if record else '' }}"
                   class="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-300"
                   placeholder="例：川菜、日料、甜点...">
            <datalist id="tag-list">
                {% for tag in tags %}
                <option value="{{ tag }}">
                {% endfor %}
            </datalist>
        </div>

        <!-- 评分 -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">⭐ 评分 *</label>
            <div class="star-rating text-2xl">
                {% for i in range(5, 0, -1) %}
                <input type="radio" name="rating" value="{{ i }}" id="star{{ i }}"
                       {% if record and record.rating == i %}checked{% elif not record and i == 5 %}checked{% endif %}>
                <label for="star{{ i }}" class="text-3xl cursor-pointer">★</label>
                {% endfor %}
            </div>
        </div>

        <!-- 经纬度（隐藏） -->
        <input type="hidden" name="latitude" id="latitude"
               value="{{ record.latitude if record else '' }}">
        <input type="hidden" name="longitude" id="longitude"
               value="{{ record.longitude if record else '' }}">
        <input type="hidden" name="location_name" id="location_name"
               value="{{ record.location_name if record else '' }}">

        <!-- 地点 -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">📍 地点 *</label>
            <div class="space-y-2">
                <p id="location-status" class="text-sm text-gray-400">
                    {% if record %}
                    {{ record.location_name or (record.latitude ~ ', ' ~ record.longitude) }}
                    {% else %}
                    正在获取定位...
                    {% endif %}
                </p>
                <button type="button" onclick="getLocation()"
                        class="px-3 py-1.5 text-sm bg-blue-100 text-blue-700 rounded-full hover:bg-blue-200 transition">
                    📡 重新定位
                </button>
                <button type="button" onclick="openMapPicker()"
                        class="px-3 py-1.5 text-sm bg-green-100 text-green-700 rounded-full hover:bg-green-200 transition">
                    🗺️ 地图选点
                </button>
                <p id="location-error" class="text-sm text-red-500 hidden"></p>
            </div>
        </div>

        <!-- 日期 -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">📅 日期 *</label>
            <input type="date" name="date_eaten" required
                   value="{{ record.date_eaten if record else today }}"
                   class="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-300">
        </div>

        <!-- 评价 -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">💬 评价</label>
            <textarea name="comment" rows="3" maxlength="1000"
                      class="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-300"
                      placeholder="好吃吗？有什么想说的...">{{ record.comment if record else '' }}</textarea>
        </div>

        <!-- 照片 -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">🖼️ 照片</label>
            {% if record and record.photo_path %}
            <div class="mb-2">
                <img src="/uploads/{{ record.photo_path }}" alt="当前照片" class="w-32 h-32 object-cover rounded-lg">
                <p class="text-xs text-gray-400 mt-1">当前照片，上传新照片会替换</p>
            </div>
            {% endif %}
            <input type="file" name="photo" accept="image/jpeg,image/png,image/webp"
                   class="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-medium file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100">
        </div>

        <!-- 提交按钮 -->
        <div class="flex gap-3 pt-2">
            <button type="submit"
                    class="flex-1 px-6 py-3 bg-orange-500 text-white font-medium rounded-xl hover:bg-orange-600 transition active:scale-95">
                {% if record %}💾 保存修改{% else %}✅ 记录美食{% endif %}
            </button>
            <a href="/" class="px-6 py-3 bg-gray-100 text-gray-600 font-medium rounded-xl hover:bg-gray-200 transition text-center">
                取消
            </a>
        </div>
    </form>
</div>
{% endblock %}

{% block head_extra %}
<script>
// 页面加载时自动获取定位
document.addEventListener('DOMContentLoaded', function() {
    const lat = document.getElementById('latitude').value;
    if (!lat) {
        getLocation();
    }
});

function getLocation() {
    const status = document.getElementById('location-status');
    const error = document.getElementById('location-error');
    error.classList.add('hidden');

    if (!navigator.geolocation) {
        status.textContent = '❌ 浏览器不支持定位功能';
        showMapFallback();
        return;
    }

    status.textContent = '📡 正在获取定位...';

    navigator.geolocation.getCurrentPosition(
        function(pos) {
            document.getElementById('latitude').value = pos.coords.latitude;
            document.getElementById('longitude').value = pos.coords.longitude;
            const lat = pos.coords.latitude.toFixed(4);
            const lng = pos.coords.longitude.toFixed(4);
            document.getElementById('location_name').value = `${lat}, ${lng}`;
            status.textContent = `📍 ${lat}, ${lng}`;
        },
        function(err) {
            console.warn('Geolocation error:', err);
            status.textContent = '⚠️ 定位失败';
            showMapFallback();
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
}

function showMapFallback() {
    const error = document.getElementById('location-error');
    error.textContent = '⏳ 定位失败，请点击「地图选点」手动选择位置';
    error.classList.remove('hidden');
}

function openMapPicker() {
    // MVP 使用一个简单的经纬度输入作为兜底
    const lat = prompt('请输入纬度（-90 到 90）：', document.getElementById('latitude').value || '');
    if (lat === null) return;
    const lng = prompt('请输入经度（-180 到 180）：', document.getElementById('longitude').value || '');
    if (lng === null) return;

    const latNum = parseFloat(lat);
    const lngNum = parseFloat(lng);
    if (isNaN(latNum) || isNaN(lngNum) || latNum < -90 || latNum > 90 || lngNum < -180 || lngNum > 180) {
        alert('经纬度超出有效范围，请重新输入');
        return;
    }

    document.getElementById('latitude').value = latNum;
    document.getElementById('longitude').value = lngNum;
    document.getElementById('location_name').value = `${latNum.toFixed(4)}, ${lngNum.toFixed(4)}`;
    document.getElementById('location-status').textContent = `📍 ${latNum.toFixed(4)}, ${lngNum.toFixed(4)}`;
}

function validateForm() {
    const lat = document.getElementById('latitude').value;
    const lng = document.getElementById('longitude').value;
    if (!lat || !lng) {
        alert('请先获取定位或选择地图位置');
        return false;
    }
    return true;
}
</script>
{% endblock %}
```

- [ ] **Step 2: 提交**

```bash
cd /home/frank/cc
git add foofie/templates/add.html
git commit -m "feat: add/edit form with location picker"
```

---

### Task 7: 菜品详情页

**文件:**
- Create: `foofie/templates/detail.html`

- [ ] **Step 1: 编写 detail.html**

`foofie/templates/detail.html`:
```html
{% extends "base.html" %}
{% block title %}{{ record.dish_name }} — Foofie{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto">
    <!-- 照片 -->
    {% if record.photo_path %}
    <div class="rounded-xl overflow-hidden mb-6 bg-gray-100 shadow-sm">
        <img src="/uploads/{{ record.photo_path }}" alt="{{ record.dish_name }}"
             class="w-full h-auto max-h-96 object-cover">
    </div>
    {% endif %}

    <!-- 基本信息卡片 -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-4">
        <div class="flex items-start justify-between">
            <div>
                <h1 class="text-2xl font-bold text-gray-900">{{ record.dish_name }}</h1>
                <p class="text-gray-500 mt-1">🏪 {{ record.restaurant }}</p>
            </div>
            <span class="tag-badge bg-orange-100 text-orange-700 text-base px-3 py-1">
                {{ record.cuisine_tag }}
            </span>
        </div>

        <!-- 评分 -->
        <div class="text-2xl text-amber-400">
            {% for i in range(record.rating) %}⭐{% endfor %}
        </div>

        <!-- 地点 -->
        {% if record.location_name %}
        <p class="text-gray-600">📍 {{ record.location_name }}</p>
        {% endif %}
        <p class="text-sm text-gray-400">
            🌐 {{ record.latitude }}, {{ record.longitude }}
        </p>

        <!-- 日期 -->
        <p class="text-sm text-gray-400">📅 {{ record.date_eaten }}</p>

        <!-- 评价 -->
        {% if record.comment %}
        <div class="bg-gray-50 rounded-lg p-4">
            <p class="text-sm text-gray-500 mb-1">💬 评价</p>
            <p class="text-gray-700 whitespace-pre-wrap">{{ record.comment }}</p>
        </div>
        {% endif %}

        <!-- 时间戳 -->
        <div class="text-xs text-gray-300 pt-2 border-t border-gray-100">
            <p>记录于 {{ record.created_at }}</p>
            {% if record.created_at != record.updated_at %}
            <p>编辑于 {{ record.updated_at }}</p>
            {% endif %}
        </div>
    </div>

    <!-- 操作按钮 -->
    <div class="flex gap-3 mt-6">
        <a href="/record/{{ record.id }}/edit"
           class="flex-1 px-6 py-3 bg-blue-500 text-white font-medium rounded-xl hover:bg-blue-600 transition text-center">
            ✏️ 编辑
        </a>
        <form method="post" action="/record/{{ record.id }}/delete"
              onsubmit="return confirm('确定要删除「{{ record.dish_name }}」吗？')"
              class="flex-1">
            <button type="submit"
                    class="w-full px-6 py-3 bg-red-50 text-red-500 font-medium rounded-xl hover:bg-red-100 transition">
                🗑️ 删除
            </button>
        </form>
    </div>

    <!-- 返回 -->
    <div class="text-center mt-4">
        <a href="/" class="text-sm text-gray-400 hover:text-gray-600 transition">← 返回列表</a>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: 提交**

```bash
cd /home/frank/cc
git add foofie/templates/detail.html
git commit -m "feat: detail page for food record"
```

---

### Task 8: 3D 地球视图 🌍

**文件:**
- Create: `foofie/templates/globe.html`

- [ ] **Step 1: 编写 globe.html（Three.js 地球）**

`foofie/templates/globe.html`:
```html
{% extends "base.html" %}
{% block title %}🌍 Foofie 美食地球{% endblock %}

{% block head_extra %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
    body { margin: 0; overflow: hidden; background: #000; }
    nav, .fixed { display: none !important; }
    #info-tooltip {
        position: fixed;
        background: rgba(0,0,0,0.8);
        color: white;
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 14px;
        pointer-events: none;
        z-index: 100;
        display: none;
        white-space: nowrap;
    }
    #back-btn {
        position: fixed;
        top: 20px;
        left: 20px;
        z-index: 50;
        background: rgba(0,0,0,0.6);
        color: white;
        border: none;
        padding: 10px 18px;
        border-radius: 24px;
        font-size: 14px;
        cursor: pointer;
        backdrop-filter: blur(4px);
        transition: background 0.2s;
    }
    #back-btn:hover { background: rgba(0,0,0,0.8); }
    #count-badge {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 50;
        background: rgba(0,0,0,0.6);
        color: white;
        padding: 8px 16px;
        border-radius: 24px;
        font-size: 14px;
        backdrop-filter: blur(4px);
    }
    #detail-popup {
        position: fixed;
        bottom: 40px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 50;
        background: rgba(0,0,0,0.85);
        backdrop-filter: blur(8px);
        color: white;
        padding: 16px 24px;
        border-radius: 16px;
        display: none;
        max-width: 320px;
        width: 90%;
        text-align: center;
    }
    #detail-popup h3 { margin: 0; font-size: 18px; font-weight: bold; }
    #detail-popup p { margin: 4px 0 0; font-size: 14px; opacity: 0.8; }
    #detail-popup a {
        display: inline-block;
        margin-top: 10px;
        padding: 6px 16px;
        background: #f97316;
        color: white;
        border-radius: 20px;
        text-decoration: none;
        font-size: 13px;
    }
    #detail-popup a:hover { background: #ea580c; }
</style>
{% endblock %}

{% block content %}
<button id="back-btn" onclick="window.location.href='/'">← 返回列表</button>
<div id="count-badge">🌍 <span id="record-count">0</span> 道美食</div>
<div id="info-tooltip"></div>
<div id="detail-popup"></div>

<script>
// 地球配置
const EARTH_RADIUS = 100;
const MARKER_SIZE = 6;
const ROTATION_SPEED = 0.0005;

// 初始化场景
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 1000);
camera.position.set(0, 50, 280);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
document.body.appendChild(renderer.domElement);

// 星空背景
const starsGeometry = new THREE.BufferGeometry();
const starsCount = 3000;
const starPositions = new Float32Array(starsCount * 3);
for (let i = 0; i < starsCount * 3; i++) {
    starPositions[i] = (Math.random() - 0.5) * 2000;
}
starsGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
const starsMaterial = new THREE.PointsMaterial({ color: 0xffffff, size: 0.8 });
const stars = new THREE.Points(starsGeometry, starsMaterial);
scene.add(stars);

// 地球纹理
const textureLoader = new THREE.TextureLoader();
const earthGeometry = new THREE.SphereGeometry(EARTH_RADIUS, 64, 64);
const earthMaterial = new THREE.MeshPhongMaterial({
    map: textureLoader.load('https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg'),
    specularMap: textureLoader.load('https://threejs.org/examples/textures/planets/earth_specular_2048.jpg'),
    specular: new THREE.Color('grey'),
    shininess: 5,
});
const earth = new THREE.Mesh(earthGeometry, earthMaterial);
scene.add(earth);

// 云层
const cloudGeometry = new THREE.SphereGeometry(EARTH_RADIUS * 1.01, 64, 64);
const cloudMaterial = new THREE.MeshPhongMaterial({
    map: textureLoader.load('https://threejs.org/examples/textures/planets/earth_clouds_1024.png'),
    transparent: true,
    opacity: 0.15,
});
const clouds = new THREE.Mesh(cloudGeometry, cloudMaterial);
scene.add(clouds);

// 光照
const ambientLight = new THREE.AmbientLight(0x333333);
scene.add(ambientLight);
const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
directionalLight.position.set(5, 3, 5);
scene.add(directionalLight);
const backLight = new THREE.DirectionalLight(0x4466ff, 0.3);
backLight.position.set(-5, 0, -5);
scene.add(backLight);

// 标记点管理
const markers = [];
const markerObjects = [];

function latLngToPosition(lat, lng, radius) {
    const phi = (90 - lat) * Math.PI / 180;
    const theta = (lng + 180) * Math.PI / 180;
    return new THREE.Vector3(
        -radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta),
    );
}

function getMarkerColor(rating) {
    if (rating <= 2) return 0xff4444;   // 红
    if (rating <= 3) return 0xffaa44;   // 黄
    return 0x44ff88;                     // 绿
}

function createMarker(data) {
    const pos = latLngToPosition(data.latitude, data.longitude, EARTH_RADIUS);
    const color = getMarkerColor(data.rating);

    // 发光光晕
    const glowGeo = new THREE.SphereGeometry(MARKER_SIZE * 1.5, 16, 16);
    const glowMat = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.25,
    });
    const glow = new THREE.Mesh(glowGeo, glowMat);
    glow.position.copy(pos);
    scene.add(glow);

    // 核心球
    const coreGeo = new THREE.SphereGeometry(MARKER_SIZE, 16, 16);
    const coreMat = new THREE.MeshBasicMaterial({ color: color });
    const core = new THREE.Mesh(coreGeo, coreMat);
    core.position.copy(pos);
    scene.add(core);

    // 脉冲光环（环状）
    const ringGeo = new THREE.RingGeometry(MARKER_SIZE * 1.8, MARKER_SIZE * 2.5, 32);
    const ringMat = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.4,
        side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.copy(pos);
    ring.lookAt(new THREE.Vector3(0, 0, 0)); // 面向球心
    scene.add(ring);

    // 连线（从标记点到地球表面）
    const linePoints = [
        pos.clone().multiplyScalar(1.05),
        pos.clone().multiplyScalar(1.3),
    ];
    const lineGeo = new THREE.BufferGeometry().setFromPoints(linePoints);
    const lineMat = new THREE.LineBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.2,
    });
    const line = new THREE.Line(lineGeo, lineMat);
    scene.add(line);

    markerObjects.push({ glow, core, ring, line, data, basePos: pos.clone(), pulsePhase: Math.random() * Math.PI * 2 });
}

// 射线检测（交互）
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let selectedMarker = null;
let isPointerDown = false;
let pointerMoved = false;
let pointerStart = { x: 0, y: 0 };
let isDragging = false;

renderer.domElement.addEventListener('pointerdown', (e) => {
    isPointerDown = true;
    pointerMoved = false;
    pointerStart.x = e.clientX;
    pointerStart.y = e.clientY;
});

renderer.domElement.addEventListener('pointermove', (e) => {
    if (isPointerDown) {
        const dx = e.clientX - pointerStart.x;
        const dy = e.clientY - pointerStart.y;
        if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
            pointerMoved = true;
        }
    }

    // hover 提示
    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);

    const cores = markerObjects.map(m => m.core);
    const intersects = raycaster.intersectObjects(cores);

    const tooltip = document.getElementById('info-tooltip');
    if (intersects.length > 0) {
        const obj = intersects[0].object;
        const marker = markerObjects.find(m => m.core === obj);
        if (marker) {
            tooltip.textContent = `${marker.data.dish_name} — ${marker.data.restaurant}`;
            tooltip.style.display = 'block';
            tooltip.style.left = (e.clientX + 15) + 'px';
            tooltip.style.top = (e.clientY - 10) + 'px';
            renderer.domElement.style.cursor = 'pointer';
            return;
        }
    }
    tooltip.style.display = 'none';
    renderer.domElement.style.cursor = 'grab';
});

renderer.domElement.addEventListener('pointerup', (e) => {
    if (pointerMoved) return; // 拖拽后不触发点击

    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);

    const cores = markerObjects.map(m => m.core);
    const intersects = raycaster.intersectObjects(cores);

    const popup = document.getElementById('detail-popup');
    if (intersects.length > 0) {
        const obj = intersects[0].object;
        const marker = markerObjects.find(m => m.core === obj);
        if (marker) {
            const d = marker.data;
            popup.innerHTML = `
                <h3>${d.dish_name}</h3>
                <p>🏪 ${d.restaurant}</p>
                <p>⭐ ${d.rating}</p>
                ${d.thumbnail_path ? `<img src="${d.thumbnail_path}" alt="" style="width:80px;height:60px;object-fit:cover;border-radius:8px;margin:8px auto;">` : ''}
                <a href="/record/${d.id}">查看详情 →</a>
            `;
            popup.style.display = 'block';
            return;
        }
    }
    popup.style.display = 'none';
    isPointerDown = false;
});

// 窗口自适应
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// 加载数据
async function loadRecords() {
    try {
        const resp = await fetch('/api/records');
        const records = await resp.json();
        document.getElementById('record-count').textContent = records.length;
        records.forEach(r => createMarker(r));
    } catch (err) {
        console.error('Failed to load records:', err);
    }
}

loadRecords();

// 拖拽旋转
let isUserInteracting = false;
let onPointerDownMouseX = 0;
let onPointerDownMouseY = 0;
let lon = 0;
let lat = 30;
let onPointerDownLon = 0;
let onPointerDownLat = 0;

renderer.domElement.addEventListener('pointerdown', (e) => {
    isUserInteracting = true;
    onPointerDownMouseX = e.clientX;
    onPointerDownMouseY = e.clientY;
    onPointerDownLon = lon;
    onPointerDownLat = lat;
});

renderer.domElement.addEventListener('pointermove', (e) => {
    if (isUserInteracting) {
        lon = (onPointerDownMouseX - e.clientX) * 0.3 + onPointerDownLon;
        lat = (e.clientY - onPointerDownMouseY) * 0.3 + onPointerDownLat;
        lat = Math.max(-85, Math.min(85, lat));
    }
});

renderer.domElement.addEventListener('pointerup', () => {
    isUserInteracting = false;
});

// 滚轮缩放
renderer.domElement.addEventListener('wheel', (e) => {
    camera.position.z += e.deltaY * 0.3;
    camera.position.z = Math.max(120, Math.min(500, camera.position.z));
});

// 触控缩放
let lastTouchDist = 0;
renderer.domElement.addEventListener('touchstart', (e) => {
    if (e.touches.length === 2) {
        lastTouchDist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
        );
    }
});
renderer.domElement.addEventListener('touchmove', (e) => {
    if (e.touches.length === 2) {
        const dist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
        );
        const delta = lastTouchDist - dist;
        camera.position.z += delta * 0.5;
        camera.position.z = Math.max(120, Math.min(500, camera.position.z));
        lastTouchDist = dist;
    }
});

// 动画循环
let time = 0;
function animate() {
    requestAnimationFrame(animate);
    time += 0.01;

    // 自动旋转（用户不交互时）
    if (!isUserInteracting) {
        lon += ROTATION_SPEED * 60;
    }

    // 云层自转
    clouds.rotation.y += 0.0003;

    // 标记点脉冲动画
    markerObjects.forEach((m, i) => {
        const phase = m.pulsePhase;
        const pulse = 1 + Math.sin(time * 2 + phase) * 0.15;
        m.glow.scale.set(pulse, pulse, pulse);
        m.glow.material.opacity = 0.2 + Math.sin(time * 2 + phase) * 0.1;
        m.ring.scale.set(pulse * 0.8, pulse * 0.8, pulse * 0.8);
        m.ring.material.opacity = 0.3 + Math.sin(time * 2 + phase) * 0.15;
    });

    // 相机旋转
    const phi = (90 - lat) * Math.PI / 180;
    const theta = lon * Math.PI / 180;
    const radius = camera.position.z;
    camera.position.x = radius * Math.sin(phi) * Math.cos(theta);
    camera.position.y = radius * Math.cos(phi);
    camera.position.z = radius * Math.sin(phi) * Math.sin(theta);
    camera.lookAt(new THREE.Vector3(0, 0, 0));

    renderer.render(scene, camera);
}

animate();
</script>
{% endblock %}
```

- [ ] **Step 2: 提交**

```bash
cd /home/frank/cc
git add foofie/templates/globe.html
git commit -m "feat: 3D earth globe with food markers and animations"
```

---

### Task 9: 本地运行验证

**没有新文件**，只需要运行并测试。

- [ ] **Step 1: 安装依赖并启动应用**

```bash
cd /home/frank/cc
pip install -r foofie/requirements.txt
```

```bash
cd /home/frank/cc
uvicorn foofie.main:app --reload --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: 浏览器验证**

打开 http://localhost:8000 验证：
- 首页列表空状态显示正常
- 添加页面表单完整，定位功能弹出浏览器权限请求
- 成功添加一条测试记录（菜名、餐厅名、选择评分等）
- 详情页显示完整
- 编辑功能正常
- 餐厅模式切换正常，分组展示
- 3D 地球页面加载，标记点显示
- 删除功能正常
- 手机端响应式布局正常（浏览器 DevTools 切换移动端模式）

- [ ] **Step 3: 提交最终版本**

```bash
cd /home/frank/cc
git add -A
git commit -m "feat: initial Foofie application complete"
```

---

## 安装与运行快速参考

```bash
# 安装依赖
cd /home/frank/cc
pip install -r foofie/requirements.txt

# 开发模式运行
uvicorn foofie.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式运行（服务器部署）
uvicorn foofie.main:app --host 0.0.0.0 --port 8000 --workers 2
```

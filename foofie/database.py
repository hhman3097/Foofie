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


ALLOWED_ORDERS = {
    "date_eaten DESC", "date_eaten ASC",
    "rating DESC", "rating ASC",
    "restaurant ASC", "restaurant DESC",
    "dish_name ASC", "dish_name DESC",
    "created_at DESC", "created_at ASC",
}


def get_all_records(order_by: str = "date_eaten DESC") -> list[sqlite3.Row]:
    if order_by not in ALLOWED_ORDERS:
        order_by = "date_eaten DESC"
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

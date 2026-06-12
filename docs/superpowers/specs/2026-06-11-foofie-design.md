# Foofie — 美食记录 Web 应用设计文档

## 概述

Foofie 是一个专为美食爱好者设计的个人美食记录 Web 应用。用户可以记录每一道吃过的菜，在地球上可视化的方式回顾自己的美食足迹。支持手机（主要录入端）和电脑（主要浏览端）的响应式适配。

## 访问边界

Foofie 作为现有聚合式网站下的子应用运行。用户登录、入口权限和子域名访问控制由上层聚合网站负责，Foofie 内部不单独实现账号体系。

Foofie 仍需做好基础输入校验、文件上传限制和错误处理，避免恶意或异常请求破坏数据。

## 核心概念

以**菜品**为基本记录单位，支持按**餐厅**聚合查看。两种视图模式可以随时切换。

## 数据模型

### FoodRecord

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | INTEGER (PK) | — | 自增主键 |
| `dish_name` | TEXT | ✓ | 菜名 |
| `restaurant` | TEXT | ✓ | 餐厅名 |
| `cuisine_tag` | TEXT | ✓ | 菜系/标签（川菜、日料、西餐、甜点…） |
| `latitude` | REAL | ✓ | 纬度（手机 GPS 获取） |
| `longitude` | REAL | ✓ | 经度 |
| `location_name` | TEXT | — | 地点文字说明（自动定位或地图选点得到，可选） |
| `rating` | INTEGER | ✓ | 评分 1–5 |
| `date_eaten` | TEXT | ✓ | 吃的日期（默认当天） |
| `comment` | TEXT | — | 评价，可选 |
| `photo_path` | TEXT | — | 照片文件路径，可选 |
| `thumbnail_path` | TEXT | — | 缩略图文件路径，可选 |
| `created_at` | TEXT | — | 记录创建时间 |
| `updated_at` | TEXT | — | 最后修改时间 |

```sql
CREATE TABLE food_records (
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
);

CREATE INDEX idx_food_records_date ON food_records(date_eaten DESC);
CREATE INDEX idx_food_records_restaurant ON food_records(restaurant);
CREATE INDEX idx_food_records_tag ON food_records(cuisine_tag);
```

MVP 阶段 `cuisine_tag` 使用单标签设计，避免过早引入多对多标签表。后续如果需要一条记录支持多个标签，再拆分为 `tags` 和 `food_record_tags`。

`date_eaten` 使用 `YYYY-MM-DD` 字符串格式。`created_at` 和 `updated_at` 统一使用服务器本地时间，与部署机器时区保持一致。编辑记录时由应用层显式更新 `updated_at`。

## 页面设计

### 响应式原则

- 使用 Tailwind CSS 的响应式断点
- 手机端（<768px）：单列布局，全宽卡片，底部导航
- 电脑端（≥768px）：多列布局，侧边栏或顶部导航
- CesiumJS 地球视图全屏显示，手机端适配触控手势和可缩放地图图层

### 1. 首页 — 美食列表

**菜品模式（默认）：**
- 顶部导航栏：应用名「Foofie」+ 搜索框 + 切换视图按钮 + 地球按钮
- 卡片列表，每张卡片展示：
  - 缩略图（如果有照片）
  - 菜名（大号）
  - 🏪 餐厅名
  - 🏷️ 标签标签（彩色气泡）
  - ⭐ 评分（星星）
  - 📍 地点文字（来自浏览器定位或地图选点，可选）
- 按日期倒序排列
- 右下角浮动「+」按钮（添加）

**餐厅模式：**
- 同一页面，切换为按餐厅分组的展示
- 每个餐厅为一个折叠面板（accordion）
- 面板标题：餐厅名 + 该餐厅收录菜数 + 平均分
- 展开后列出该餐厅的所有菜品卡片

**搜索与筛选：**
- 搜索框实时匹配：菜名、餐厅名、标签
- 按标签筛选的下拉

### 2. 添加/编辑页面

- 表单页，字段排列：
  - 🍽️ 菜名（input）
  - 🏪 餐厅名（input）
  - 🏷️ 菜系/标签（input / 推荐下拉，可自定义输入）
  - ⭐ 评分（1–5 星点击选择）
  - 📍 地点（优先自动获取 GPS 经纬度；失败或不准确时打开地图选点）
  - 📅 日期（date picker，默认当天）
  - 💬 评价（textarea，可选）
  - 🖼️ 照片（file input，可选）
- 底部「保存」按钮
- 编辑时预填原有数据

### 定位交互

- 新增记录时自动请求浏览器定位，并展示定位状态。
- 定位成功后写入隐藏的 `latitude` / `longitude` 字段，并尽量显示地点文字。
- 如果用户拒绝定位、定位超时或定位明显不准，页面提供「在地图上选点」入口。
- 地图选点完成后同样写入经纬度。用户不需要手动填写经纬度数字。
- 保存前必须有有效经纬度；服务端同时校验纬度和经度范围。
- MVP 可以先使用轻量地图选点页或第三方地图组件；如果暂不接入完整地图服务，至少提供一个可点击的简化地图/经纬网兜底。

### 3. CesiumJS 地球视图 🌍

- 全屏渲染 CesiumJS 地球
- 底图使用可缩放瓦片影像图层，默认街道图，支持切换卫星图和暗色图
- 数据标记使用独立的美食点位图层：
  - 每个点位对应一道菜
  - 点位颜色按评分区分（1-2 红、3 黄、4 绿、5 青）
  - 点位大小按评分增强
- 图层控制：
  - 美食点位图层开关
  - 最低评分筛选
  - 底图切换
- 交互：
  - 鼠标/手指拖拽旋转地球
  - 滚轮/双指缩放地图层级
  - 点击显示弹出卡片：菜名、餐厅名、评分、照片缩略图、「查看详情」链接
- 右上角「返回列表」按钮
- 手机端适配触控手势

### 4. 菜品详情页

- 大图展示（如果有照片）
- 所有字段完整显示
- 右上角「编辑」和「删除」按钮
- 底部「返回」

## 技术栈

| 层级 | 选型 | 理由 |
|------|------|------|
| 后端框架 | FastAPI (Python) | 轻量、异步、自动 API 文档，内存占用低 |
| 数据库 | SQLite | 无额外进程，单文件备份，适合个人应用 |
| 模板引擎 | Jinja2 | FastAPI 原生支持 |
| CSS 框架 | Tailwind CSS (CDN) | 零构建步骤，响应式开箱即用 |
| 地球/GIS 渲染 | CesiumJS (CDN) | 专业 3D 地球、可缩放瓦片图层、图层管理能力成熟 |
| 反向代理 | Nginx | 静态文件服务、SSL 终止 |
| 部署 | Uvicorn + Nginx + Let's Encrypt | 两核 4G 服务器绰绰有余 |

**为什么不用前端框架（React/Vue）：**

- 页面数量少（4 个视图），SPA 反而增加复杂度
- 不需要客户端路由、状态管理等重型能力
- 省去构建步骤，部署就是复制文件
- Tailwind + Jinja2 组合可以做出完全响应式的界面

生产环境可先使用 CDN 资源以降低构建复杂度，但需要固定版本号。若后续需要更强的离线能力或减少第三方依赖，再将 Tailwind、CesiumJS 和地图相关资源下载到本地静态目录。

## API 设计

### RESTful 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 首页（列表视图） |
| GET | `/add` | 添加页面 |
| POST | `/add` | 提交新记录 |
| GET | `/record/{id}` | 详情页 |
| GET | `/record/{id}/edit` | 编辑页面 |
| POST | `/record/{id}/edit` | 提交编辑 |
| POST | `/record/{id}/delete` | 删除记录 |
| GET | `/globe` | 3D 地球视图 |
| GET | `/api/records` | JSON：所有记录（地球用） |
| GET | `/api/records?restaurant=xxx` | JSON：按餐厅筛选 |
| GET | `/api/records?tag=xxx` | JSON：按标签筛选 |
| GET | `/api/records/search?q=xxx` | JSON：搜索 |

### 照片处理

- 上传到 `uploads/` 目录
- 文件名格式：`{uuid}.{ext}`，不直接使用用户上传的原始文件名
- 访问路径：`/uploads/{filename}`
- 限制文件大小（建议 <5MB）
- 限制格式：jpg/jpeg/png/webp
- 服务端校验扩展名和 MIME 类型
- 上传目录只作为静态文件目录，不允许执行脚本
- 删除记录时同步删除对应照片文件
- 生成缩略图并保存到 `thumbnails/`，路径写入 `thumbnail_path`
- 列表页优先使用缩略图，避免直接加载手机原图

## 数据流

### 添加记录流程

```
用户打开 /add
  → 浏览器请求 GPS 定位（navigator.geolocation）
  → 定位成功则填入经纬度到隐藏字段
  → 定位失败或用户认为位置不准，则打开地图选点
  → 地图选点后填入经纬度到隐藏字段
  → 用户填写其他字段
  → 提交表单（POST /add，multipart/form-data）
  → FastAPI 验证数据
    → 校验经纬度范围、评分范围、日期格式和文本长度
    → 如有照片，保存到 uploads/ 并生成 thumbnails/
    → INSERT 到 SQLite
  → 重定向到详情页或列表页
```

### CesiumJS 地球加载流程

```
用户点击「地球」按钮
  → GET /globe 返回 HTML 页面（含 CesiumJS CDN 引用）
  → 页面加载后 JS 发起 GET /api/records
  → 返回 JSON 数组
  → CesiumJS 创建美食点位图层并渲染标记点
  → 用户可切换底图、隐藏/显示美食点位、按最低评分筛选
```

### 餐厅模式聚合流程

```
用户切换至「餐厅模式」
  → GET / 加查询参数 ?view=restaurant
  → FastAPI 执行聚合查询：
    SELECT restaurant, COUNT(*) as count, AVG(rating) as avg_rating
    FROM food_records GROUP BY restaurant ORDER BY count DESC
  → 再一次性查询所有菜品，按 restaurant、date_eaten 排序
  → 在 Python 中按餐厅分组，避免每个餐厅一次查询
  → Jinja2 渲染折叠面板
```

## 目录结构

```
foofie/
├── main.py              # FastAPI 入口
├── database.py          # SQLite 连接与初始化
├── models.py            # 数据模型定义
├── requirements.txt     # Python 依赖
├── templates/           # Jinja2 模板
│   ├── base.html        # 基础模板（导航 + 布局）
│   ├── index.html       # 列表页（菜品/餐厅模式）
│   ├── add.html         # 添加页
│   ├── edit.html        # 编辑页
│   ├── detail.html      # 详情页
│   └── globe.html       # 3D 地球页
├── static/
│   └── css/
│       └── style.css    # 自定义样式（少量）
├── uploads/             # 上传的原图
├── thumbnails/          # 列表缩略图
└── foofie.db            # SQLite 数据库文件
```

## 部署方案

### 开发阶段（本地）
```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 生产部署（服务器）
1. 将项目文件 scp 到服务器
2. 安装依赖
3. 配置 Nginx 反向代理 + Let's Encrypt SSL
4. 接入上层聚合网站的登录与子域名访问控制
5. 使用 systemd 托管 Uvicorn 进程

```nginx
# Nginx 配置示例
server {
    server_name foofie.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /uploads/ {
        alias /path/to/foofie/uploads/;
    }

    location /thumbnails/ {
        alias /path/to/foofie/thumbnails/;
    }

    client_max_body_size 10M;
}
```

## 后续可能的扩展（暂不实现）

- Foofie 内置用户登录/多用户支持
- 餐厅详情独立页面（含评分/地址/照片墙）
- 美食地图热力图
- 数据导出（CSV/JSON）
- 批量导入
- 点评/二刷功能
- 统计面板（按年份、按菜系、按地区的食迹统计）

## 非功能性需求

- **响应式**：完美适配手机（录入端）和电脑（浏览端）
- **轻量**：内存占用 <200MB，两核 4G 服务器无压力
- **缓存友好**：核心资源依赖 CDN 时，首次加载需要网络；首次加载后 CSS/JS 可由浏览器缓存。若需要真正离线使用，后续改为本地静态资源或 PWA。
- **数据安全**：SQLite 文件定期备份，照片文件一并备份

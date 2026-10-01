"""
霸王茶姬销量数据分析平台 - 数据层

职责：SQLite 连接管理、建表/索引、CSV 数据导入、查询与缓存。
路由层见 app.py。
"""

import os
import csv
import sqlite3
import threading
from collections import OrderedDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATA_PATH = os.path.join(BASE_DIR, "data", "bawangchaji_sales.csv")
# 允许通过环境变量指定数据库位置（测试用临时库时很方便）
DB_PATH = os.environ.get(
    "TEA_DB_PATH", os.path.join(BASE_DIR, "backend", "bawangchaji.db")
)

# schema 结构变化时递增；启动时发现版本不一致会自动 DROP 重建
SCHEMA_VERSION = "2"

INSERT_SQL = """
    INSERT INTO sales (
        date, city, store_id, product_name, product_category,
        unit_price, quantity, discount, paid_amount,
        weather, season, is_holiday, marketing_activity
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# 运行期数据不变，查询结果可以安全地进程内缓存；重新导入后清空
# OrderedDict 实现 LRU：命中移到末尾，超限时淘汰最久未用的键，避免长跑下缓存无界增长
_CACHE_MAX = 256
_cache = OrderedDict()
_cache_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def clear_cache():
    with _cache_lock:
        _cache.clear()


def query(sql, params=(), use_cache=True):
    """执行查询，返回 dict 列表。异常时保证连接被关闭。"""
    if use_cache:
        key = (sql, tuple(params))
        with _cache_lock:
            if key in _cache:
                _cache.move_to_end(key)
                return _cache[key]

    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        result = [dict(r) for r in rows]
    finally:
        conn.close()

    if use_cache:
        with _cache_lock:
            _cache[key] = result
            _cache.move_to_end(key)
            while len(_cache) > _CACHE_MAX:
                _cache.popitem(last=False)
    return result


def _create_schema(conn):
    """（重）建表与索引。结构变更随 SCHEMA_VERSION 一起升级。"""
    conn.execute("DROP TABLE IF EXISTS sales")
    conn.execute(
        """
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            city TEXT,
            store_id TEXT,
            product_name TEXT,
            product_category TEXT,
            unit_price REAL,
            quantity INTEGER,
            discount REAL,
            paid_amount REAL,
            weather TEXT,
            season TEXT,
            is_holiday TEXT,
            marketing_activity TEXT
        )
        """
    )
    for column in ("date", "city", "product_name", "product_category", "season", "weather"):
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_sales_{column} ON sales({column})")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
    )


def _parse_row(row):
    """把一行 CSV 转成插入参数；字段缺失或数值非法时抛 ValueError/KeyError。"""
    return (
        row["日期"],
        row["城市"],
        row["门店编号"],
        row["产品名称"],
        row["产品类别"],
        float(row["单价(元)"]),
        int(row["销量(杯)"]),
        float(row["折扣(元)"]),
        float(row["销售额(元)"]),
        row.get("天气", ""),
        row.get("季节", ""),
        row.get("是否节假日", ""),
        row.get("营销活动", ""),
    )


def _import_csv(conn):
    """批量导入 CSV，返回 (成功行数, 跳过的坏行数)。"""
    imported = 0
    skipped = 0
    batch = []
    with open(DATA_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                batch.append(_parse_row(row))
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            if len(batch) >= 1000:
                conn.executemany(INSERT_SQL, batch)
                imported += len(batch)
                batch = []
        if batch:
            conn.executemany(INSERT_SQL, batch)
            imported += len(batch)
    return imported, skipped


def init_db():
    """
    启动时调用：
    1. 建表；schema 版本变化 -> DROP 重建
    2. CSV 修改时间变化或表为空 -> 重新导入（个别坏行跳过，不影响整体）
    3. CSV 缺失 -> 保留现有库继续运行，仅打印警告
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        stored_version = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        schema_changed = stored_version is None or stored_version[0] != SCHEMA_VERSION
        if schema_changed:
            _create_schema(conn)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, city TEXT, store_id TEXT,
                product_name TEXT, product_category TEXT,
                unit_price REAL, quantity INTEGER, discount REAL, paid_amount REAL,
                weather TEXT, season TEXT, is_holiday TEXT, marketing_activity TEXT
            )
            """
        )

        if not os.path.exists(DATA_PATH):
            print(f"[init_db] 警告：未找到数据文件 {DATA_PATH}，使用现有数据库（可能为空）")
            return

        current_mtime = str(os.path.getmtime(DATA_PATH))
        stored_mtime_row = conn.execute(
            "SELECT value FROM meta WHERE key = 'csv_mtime'"
        ).fetchone()
        row_count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        mtime_changed = (
            stored_mtime_row is None or stored_mtime_row[0] != current_mtime
        )

        if not schema_changed and not mtime_changed and row_count > 0:
            print(f"[init_db] 数据无变化，跳过导入（{row_count} 行）")
            return

        if not schema_changed:
            conn.execute("DELETE FROM sales")
        imported, skipped = _import_csv(conn)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('csv_mtime', ?)",
            (current_mtime,),
        )
        conn.commit()
        clear_cache()
        print(f"[init_db] 导入完成：成功 {imported} 行，跳过坏行 {skipped} 行")
    finally:
        conn.close()

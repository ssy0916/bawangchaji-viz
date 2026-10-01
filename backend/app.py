"""霸王茶姬销量数据分析可视化平台 - FastAPI 路由层。"""

import csv
import io
import os
import socket
import sqlite3
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

try:
    from .db import FRONTEND_DIR, get_conn, init_db, query
except ImportError:
    from db import FRONTEND_DIR, get_conn, init_db, query

app = FastAPI(title="霸王茶姬销量分析平台")
app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


def _valid_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except (TypeError, ValueError):
        return None


def build_filter_where_and_params(args):
    conditions = []
    params = []
    for key, column in (("city", "city"), ("product", "product_name"), ("category", "product_category"), ("season", "season"), ("weather", "weather")):
        if args.get(key):
            conditions.append(f"{column} = ?")
            params.append(args.get(key))
    start_date = args.get("start_date") or None
    end_date = args.get("end_date") or None
    if start_date and _valid_date(start_date) is None:
        raise HTTPException(400, "start_date 格式无效，应为 YYYY-MM-DD")
    if end_date and _valid_date(end_date) is None:
        raise HTTPException(400, "end_date 格式无效，应为 YYYY-MM-DD")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, "start_date 不能晚于 end_date")
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    return (" WHERE " + " AND ".join(conditions)) if conditions else "", params


@app.middleware("http")
async def require_api_key_if_enabled(request: Request, call_next):
    if os.environ.get("TEA_REQUIRE_AUTH", "0") != "1":
        return await call_next(request)
    if request.url.path == "/api/health" or not request.url.path.startswith("/api/"):
        return await call_next(request)
    expected_key = os.environ.get("TEA_API_KEY", "")
    if not expected_key:
        return JSONResponse({"error": "api_key_not_configured"}, status_code=500)
    authorization = request.headers.get("Authorization", "")
    received_key = authorization[7:].strip() if authorization.startswith("Bearer ") else request.headers.get("X-API-Key", "")
    if received_key != expected_key:
        return JSONResponse({"error": "unauthorized", "message": "Missing or invalid API key"}, status_code=401)
    return await call_next(request)


def _args(request):
    return request.query_params


def _filtered_query(request, sql):
    where_clause, params = build_filter_where_and_params(_args(request))
    return query(sql.format(where_clause=where_clause), params)


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/health")
def api_health():
    try:
        sample = query("SELECT COUNT(*) AS total_records FROM sales", use_cache=False)
    except sqlite3.Error as exc:
        return JSONResponse({"status": "degraded", "service": "tea-sales-dashboard", "db": "error", "message": str(exc)}, status_code=500)
    return {"status": "ok", "service": "tea-sales-dashboard", "db": "ok" if sample else "empty", "total_records": sample[0]["total_records"] if sample else 0}


@app.get("/api/filters")
def api_filters():
    return {
        "cities": [r["city"] for r in query("SELECT city FROM sales GROUP BY city ORDER BY city")],
        "products": [r["product"] for r in query("SELECT product_name AS product FROM sales GROUP BY product_name ORDER BY product")],
        "categories": [r["category"] for r in query("SELECT product_category AS category FROM sales GROUP BY product_category ORDER BY category")],
        "seasons": [r["season"] for r in query("SELECT season FROM sales GROUP BY season ORDER BY season")],
        "weather": [r["weather"] for r in query("SELECT weather FROM sales GROUP BY weather ORDER BY weather")],
    }


@app.get("/api/export")
def api_export(request: Request):
    where_clause, params = build_filter_where_and_params(_args(request))
    conn = get_conn()
    try:
        rows = conn.execute(f"SELECT date, city, store_id, product_name, product_category, unit_price, quantity, discount, paid_amount, weather, season, is_holiday, marketing_activity FROM sales {where_clause} ORDER BY date ASC, city ASC, product_name ASC", params).fetchall()
    finally:
        conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "city", "store_id", "product_name", "product_category", "unit_price", "quantity", "discount", "paid_amount", "weather", "season", "is_holiday", "marketing_activity"])
    writer.writerows(rows)
    response = Response(output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=tea_sales_export.csv"
    return response


@app.get("/api/summary")
def api_summary(request: Request):
    rows = _filtered_query(request, "SELECT COUNT(*) AS total_records, COALESCE(SUM(quantity), 0) AS total_qty, COALESCE(SUM(paid_amount), 0) AS total_revenue FROM sales {where_clause}")
    return rows[0] if rows else {"total_records": 0, "total_qty": 0, "total_revenue": 0}


@app.get("/api/monthly")
def api_monthly(request: Request):
    return _filtered_query(request, "SELECT strftime('%Y-%m', date) AS month, SUM(quantity) AS qty, SUM(paid_amount) AS revenue FROM sales {where_clause} GROUP BY month ORDER BY month")


@app.get("/api/product_rank")
def api_product_rank(request: Request):
    return _filtered_query(request, "SELECT product_name AS product, SUM(quantity) AS qty FROM sales {where_clause} GROUP BY product_name ORDER BY qty DESC")


@app.get("/api/category_pie")
def api_category_pie(request: Request):
    return _filtered_query(request, "SELECT product_category AS category, SUM(quantity) AS qty FROM sales {where_clause} GROUP BY category ORDER BY qty DESC")


@app.get("/api/city_rank")
def api_city_rank(request: Request):
    return _filtered_query(request, "SELECT city, SUM(quantity) AS qty, SUM(paid_amount) AS revenue FROM sales {where_clause} GROUP BY city ORDER BY qty DESC")


@app.get("/api/season")
def api_season(request: Request):
    return _filtered_query(request, "SELECT season, SUM(quantity) AS qty, SUM(paid_amount) AS revenue FROM sales {where_clause} GROUP BY season")


@app.get("/api/weather")
def api_weather(request: Request):
    return _filtered_query(request, "SELECT weather, AVG(quantity) AS avg_qty, SUM(quantity) AS total_qty FROM sales {where_clause} GROUP BY weather ORDER BY avg_qty DESC")


@app.get("/api/campaign")
def api_campaign(request: Request):
    return _filtered_query(request, "SELECT marketing_activity AS activity, AVG(quantity) AS avg_qty, AVG(paid_amount) AS avg_revenue, COUNT(*) AS record_count FROM sales {where_clause} GROUP BY marketing_activity ORDER BY avg_qty DESC")


@app.get("/api/city_product")
def api_city_product(request: Request):
    rows = _filtered_query(request, "SELECT city, product_name AS product, SUM(quantity) AS qty FROM sales {where_clause} GROUP BY city, product_name")
    cities = sorted({r["city"] for r in rows})
    products = sorted({r["product"] for r in rows})
    city_index = {city: i for i, city in enumerate(cities)}
    product_index = {product: i for i, product in enumerate(products)}
    return {"cities": cities, "products": products, "data": [[product_index[r["product"]], city_index[r["city"]], r["qty"] or 0] for r in rows]}


@app.get("/api/holiday")
def api_holiday(request: Request):
    return _filtered_query(request, "SELECT is_holiday, AVG(quantity) AS avg_qty, AVG(paid_amount) AS avg_revenue FROM sales {where_clause} GROUP BY is_holiday")


@app.get("/api/discount")
def api_discount(request: Request):
    return _filtered_query(request, "SELECT discount, AVG(quantity) AS avg_qty, SUM(quantity) AS total_qty FROM sales {where_clause} GROUP BY discount ORDER BY discount")


@app.get("/api/insights")
def api_insights(request: Request):
    where_clause, params = build_filter_where_and_params(_args(request))
    total = query(f"SELECT COUNT(*) AS records, COALESCE(SUM(quantity), 0) AS qty, COALESCE(AVG(paid_amount), 0) AS avg_record_revenue FROM sales {where_clause}", params)[0]
    if not total["records"]:
        return {"insights": []}
    total_qty = total["qty"]

    def share(part):
        return round(part * 100.0 / total_qty, 1) if total_qty else 0.0

    def lift(value, baseline):
        return round((value - baseline) * 100.0 / baseline, 1) if baseline else 0.0

    cities = query(f"SELECT city AS name, SUM(quantity) AS qty FROM sales {where_clause} GROUP BY city ORDER BY qty DESC", params)
    products = query(f"SELECT product_name AS name, SUM(quantity) AS qty FROM sales {where_clause} GROUP BY product_name ORDER BY qty DESC", params)
    categories = query(f"SELECT product_category AS name, SUM(quantity) AS qty FROM sales {where_clause} GROUP BY product_category ORDER BY qty DESC", params)
    months = query(f"SELECT strftime('%Y-%m', date) AS name, SUM(quantity) AS qty FROM sales {where_clause} GROUP BY name ORDER BY qty DESC", params)
    weather = query(f"SELECT weather AS name, AVG(quantity) AS avg_qty, SUM(quantity) AS qty FROM sales {where_clause} GROUP BY weather ORDER BY avg_qty DESC", params)
    holiday_rows = query(f"SELECT is_holiday AS flag, AVG(quantity) AS avg_qty FROM sales {where_clause} GROUP BY is_holiday", params)
    holiday_avg = {("是" if r["flag"] in ("是", "1") else "否"): r["avg_qty"] for r in holiday_rows}
    campaign_rows = query(f"SELECT marketing_activity AS name, AVG(quantity) AS avg_qty, COUNT(*) AS records FROM sales {where_clause} GROUP BY marketing_activity ORDER BY avg_qty DESC", params)
    campaign_by_name = {r["name"]: r for r in campaign_rows}
    discount_rows = query(f"SELECT discount AS tier, AVG(quantity) AS avg_qty FROM sales {where_clause} GROUP BY discount ORDER BY discount", params)
    insights = []
    if cities:
        top = cities[0]
        insights.append({"title": "头部城市", "metric": f"{top['name']} · {share(top['qty'])}%", "detail": f"销量 {top['qty']:,} 杯，占当前范围总销量（{total_qty:,} 杯）的 {share(top['qty'])}%，前 3 城合计 {share(sum(r['qty'] for r in cities[:3]))}%"})
    if products:
        top = products[0]
        insights.append({"title": "爆款产品", "metric": f"{top['name']} · {share(top['qty'])}%", "detail": f"销量 {top['qty']:,} 杯，占总销量 {share(top['qty'])}%，前 3 产品合计 {share(sum(r['qty'] for r in products[:3]))}%"})
    if categories:
        top = categories[0]
        insights.append({"title": "主力品类", "metric": f"{top['name']} · {share(top['qty'])}%", "detail": "、".join(f"{r['name']} {share(r['qty'])}%" for r in categories)})
    if months:
        top = months[0]
        average = total_qty / len(months)
        insights.append({"title": "最旺月份", "metric": f"{top['name']} · {top['qty']:,} 杯", "detail": f"高于月均 {average:,.0f} 杯约 {lift(top['qty'], average)}%"})
    if len(weather) >= 2:
        best, worst = weather[0], weather[-1]
        insights.append({"title": "天气影响", "metric": f"{best['name']}天均销最高", "detail": f"{best['name']} 天平均 {best['avg_qty']:.0f} 杯/条，{worst['name']} 天平均 {worst['avg_qty']:.0f} 杯/条，相差 {lift(best['avg_qty'], worst['avg_qty'])}%"})
    if "是" in holiday_avg and "否" in holiday_avg:
        yes, no = holiday_avg["是"], holiday_avg["否"]
        insights.append({"title": "节假日效应", "metric": f"{'节假日更高' if yes >= no else '非节假日更高'} · 相差 {abs(lift(yes, no))}%", "detail": f"节假日平均 {yes:.0f} 杯/条，非节假日平均 {no:.0f} 杯/条"})
    if campaign_by_name.get("无"):
        promoted = [r for r in campaign_rows if r["name"] != "无"]
        if promoted:
            best = promoted[0]
            baseline = campaign_by_name["无"]["avg_qty"]
            insights.append({"title": "最佳营销活动", "metric": f"{best['name']} · {lift(best['avg_qty'], baseline):+}%", "detail": f"平均 {best['avg_qty']:.0f} 杯/条（无活动基线 {baseline:.0f} 杯/条，{best['records']:,} 条记录）"})
    if len(discount_rows) >= 2:
        no_discount = next((r for r in discount_rows if float(r["tier"]) == 0), None)
        deepest = discount_rows[-1]
        if no_discount and float(deepest["tier"]) > 0:
            insights.append({"title": "减免促销效果", "metric": f"减 {deepest['tier']:g} 元 · {lift(deepest['avg_qty'], no_discount['avg_qty']):+}%", "detail": f"平均 {deepest['avg_qty']:.0f} 杯/条，无减免时 {no_discount['avg_qty']:.0f} 杯/条"})
    return {"insights": insights, "summary": {"total_qty": total_qty, "total_records": total["records"], "avg_record_revenue": round(total["avg_record_revenue"], 1)}}


@app.exception_handler(HTTPException)
async def handle_http_error(request: Request, error: HTTPException):
    if error.status_code == 400:
        return JSONResponse({"error": "bad_request", "message": error.detail}, status_code=400)
    return JSONResponse({"error": "http_error", "message": error.detail}, status_code=error.status_code)


@app.exception_handler(sqlite3.Error)
async def handle_db_error(request: Request, error: sqlite3.Error):
    return JSONResponse({"error": "database_error", "message": str(error)}, status_code=500)


def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    import uvicorn

    init_db()
    host = os.environ.get("TEA_HOST", "0.0.0.0")
    port = int(os.environ.get("TEA_PORT", "8080"))
    debug = os.environ.get("TEA_DEBUG", "0") == "1"
    if debug and host == "0.0.0.0":
        host = "127.0.0.1"
    print(f"服务启动（debug={debug}）：http://127.0.0.1:{port}")
    if host == "0.0.0.0":
        print(f"局域网访问：http://{get_lan_ip()}:{port}")
    uvicorn.run(app, host=host, port=port, reload=False)

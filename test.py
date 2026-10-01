"""
霸王茶姬销量分析平台 - 后端接口冒烟测试

运行方式（项目根目录）：
    python test.py
或：
    python -m unittest test.py

测试会使用临时数据库，不影响 backend/bawangchaji.db。
"""

import csv
import os
import sys
import tempfile
import unittest

# TEA_DB_PATH 必须在 import db/app 之前设置，让测试走临时数据库
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["TEA_DB_PATH"] = _tmp.name

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND_DIR)

import db  # noqa: E402
import app as app_module  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "bawangchaji_sales.csv")


class SalesApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.client = TestClient(app_module.app)
        with open(CSV_PATH, encoding="utf-8", newline="") as f:
            cls.csv_rows = sum(1 for _ in csv.DictReader(f))

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(_tmp.name)
        except OSError:
            pass

    def _get_json(self, url):
        resp = self.client.get(url)
        try:
            self.assertEqual(resp.status_code, 200, f"{url} 应返回 200")
            self.assertTrue(resp.headers.get("content-type", "").startswith("application/json"), f"{url} 应返回 JSON")
            return resp.json()
        finally:
            resp.close()

    def test_index(self):
        resp = self.client.get("/")
        try:
            self.assertEqual(resp.status_code, 200)
            self.assertIn("销量数据分析平台".encode("utf-8"), resp.content)
        finally:
            resp.close()

    def test_static_assets(self):
        for url in ("/css/style.css", "/js/chart.js", "/js/echarts.min.js"):
            resp = self.client.get(url)
            try:
                self.assertEqual(resp.status_code, 200, f"{url} 应可访问")
            finally:
                resp.close()

    def test_health(self):
        data = self._get_json("/api/health")
        self.assertEqual(data["status"], "ok")
        self.assertIn("service", data)
        self.assertIn("db", data)

    def test_summary(self):
        data = self._get_json("/api/summary")
        self.assertEqual(data["total_records"], self.csv_rows)
        self.assertGreater(data["total_qty"], 0)
        self.assertGreater(data["total_revenue"], 0)
        self.assertNotIn("avg_member", data)

    def test_monthly(self):
        data = self._get_json("/api/monthly")
        self.assertEqual(len(data), 12)
        self.assertIn("month", data[0])
        self.assertIn("qty", data[0])
        self.assertIn("revenue", data[0])

    def test_campaign(self):
        data = self._get_json("/api/campaign")
        activities = {row["activity"] for row in data}
        self.assertEqual(activities, {"无", "会员日", "满减优惠", "新品上市"})
        self.assertIn("avg_qty", data[0])
        self.assertIn("avg_revenue", data[0])
        self.assertIn("record_count", data[0])

    def test_city_product_heatmap(self):
        data = self._get_json("/api/city_product")
        self.assertIn("cities", data)
        self.assertIn("products", data)
        self.assertIn("data", data)
        self.assertTrue(data["cities"] and data["products"])
        for triple in data["data"]:
            self.assertEqual(len(triple), 3)
            x, y, value = triple
            self.assertLess(x, len(data["products"]))
            self.assertLess(y, len(data["cities"]))
            self.assertGreaterEqual(value, 0)

    def test_discount(self):
        data = self._get_json("/api/discount")
        values = sorted(float(row["discount"]) for row in data)
        self.assertEqual(values, [0.0, 2.0, 3.0])

    def test_holiday_groups(self):
        data = self._get_json("/api/holiday")
        labels = {row["is_holiday"] for row in data}
        self.assertTrue(labels <= {"是", "否", "1", "0", ""})

    def test_filters_endpoint(self):
        data = self._get_json("/api/filters")
        self.assertIn("cities", data)
        self.assertIn("products", data)
        self.assertIn("categories", data)
        self.assertIn("seasons", data)
        self.assertIn("weather", data)

    def test_export_endpoint(self):
        resp = self.client.get("/api/export")
        try:
            self.assertEqual(resp.status_code, 200)
            self.assertIn("text/csv", resp.headers.get("content-type", ""))
            self.assertIn("date,city", resp.text)
        finally:
            resp.close()

    def test_chart_endpoint_filtering_consistency(self):
        resp = self.client.get("/api/monthly?city=北京&product=珍珠乌龙&category=茶&season=夏季&weather=晴&start_date=2024-01-01&end_date=2024-12-31")
        try:
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIsInstance(data, list)
        finally:
            resp.close()

    def test_summary_filter_matches_db(self):
        """筛选后的汇总必须与直接查库结果一致，且不超过全量。"""
        city = "北京"
        data = self._get_json(f"/api/summary?city={city}")
        expected = db.query(
            "SELECT COUNT(*) AS c, COALESCE(SUM(quantity), 0) AS q FROM sales WHERE city = ?",
            (city,),
            use_cache=False,
        )[0]
        self.assertEqual(data["total_records"], expected["c"])
        self.assertEqual(data["total_qty"], expected["q"])

        full = self._get_json("/api/summary")
        self.assertLess(data["total_records"], full["total_records"])

    def test_summary_date_range_empty(self):
        """不可能的日期范围应返回零值而不是报错。"""
        data = self._get_json("/api/summary?start_date=2099-01-01&end_date=2099-12-31")
        self.assertEqual(data["total_records"], 0)
        self.assertEqual(data["total_qty"], 0)
        self.assertEqual(data["total_revenue"], 0)

    def test_export_filtered_csv(self):
        """导出 CSV 必须只包含被筛选城市的数据，行数与接口一致。"""
        city = "上海"
        resp = self.client.get(f"/api/export?city={city}")
        try:
            self.assertEqual(resp.status_code, 200)
            text = resp.text
            lines = [ln for ln in text.strip().splitlines() if ln]
            header, rows = lines[0], lines[1:]
            self.assertEqual(header.split(",")[1], "city")
            self.assertTrue(rows, "筛选结果不应为空")
            for line in rows:
                self.assertEqual(line.split(",")[1], city)
            expected = self._get_json(f"/api/summary?city={city}")
            self.assertEqual(len(rows), expected["total_records"])
        finally:
            resp.close()

    def test_insights_structure_and_values(self):
        data = self._get_json("/api/insights")
        self.assertIn("insights", data)
        self.assertGreaterEqual(len(data["insights"]), 5)
        for card in data["insights"]:
            self.assertEqual(set(card.keys()), {"title", "metric", "detail"})
            self.assertTrue(card["title"] and card["metric"] and card["detail"])
        titles = {card["title"] for card in data["insights"]}
        self.assertIn("头部城市", titles)
        self.assertIn("爆款产品", titles)

    def test_insights_empty_when_no_data(self):
        data = self._get_json("/api/insights?start_date=2099-01-01")
        self.assertEqual(data["insights"], [])

    def test_query_cache_hits(self):
        """相同参数的第二次请求应命中进程内缓存，返回结果一致。"""
        db.clear_cache()
        first = self._get_json("/api/city_rank")
        cache_size_after_first = len(db._cache)
        self.assertGreater(cache_size_after_first, 0)
        second = self._get_json("/api/city_rank")
        self.assertEqual(first, second)

    def test_invalid_date_returns_400_json(self):
        """非法日期格式必须返回 400 + JSON 错误体，而不是静默查错数据。"""
        for url in (
            "/api/summary?start_date=2025-13-01",
            "/api/monthly?end_date=not-a-date",
            "/api/insights?start_date=2025/01/01",
        ):
            resp = self.client.get(url)
            try:
                self.assertEqual(resp.status_code, 400, url)
                self.assertTrue(resp.headers.get("content-type", "").startswith("application/json"), url)
                self.assertEqual(resp.json()["error"], "bad_request")
            finally:
                resp.close()

    def test_reversed_date_range_returns_400(self):
        """开始日期晚于结束日期必须返回 400。"""
        resp = self.client.get("/api/summary?start_date=2025-06-01&end_date=2025-01-01")
        try:
            self.assertEqual(resp.status_code, 400)
            self.assertIn("start_date", resp.json()["message"])
        finally:
            resp.close()

    def test_valid_date_still_works(self):
        """合法日期范围不受校验影响。"""
        data = self._get_json("/api/summary?start_date=2025-01-01&end_date=2025-01-31")
        self.assertGreater(data["total_records"], 0)

    def test_cache_lru_eviction(self):
        """缓存达到上限后应淘汰最久未用的键，而不是无限增长。"""
        original_max = db._CACHE_MAX
        db._CACHE_MAX = 3
        db.clear_cache()
        try:
            for i in range(5):
                db.query("SELECT ? AS v", (i,))
            self.assertEqual(len(db._cache), 3)
            # 最早的两个键应已被淘汰，最新的保留
            self.assertNotIn(("SELECT ? AS v", (0,)), db._cache)
            self.assertNotIn(("SELECT ? AS v", (1,)), db._cache)
            self.assertIn(("SELECT ? AS v", (4,)), db._cache)
        finally:
            db._CACHE_MAX = original_max
            db.clear_cache()


if __name__ == "__main__":
    unittest.main(verbosity=2)

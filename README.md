# 霸王茶姬销量数据分析平台

基于 **Python + FastAPI + SQLite + 原生 JavaScript + ECharts** 的销量数据可视化分析平台。
从 6.2 万条门店销售记录出发，完成「CSV → SQLite → REST API → 可视化大屏 + 自动洞察」的完整数据链路，
支持多维联动筛选、CSV 导出，并可一键部署供本机及同一局域网访问。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10、FastAPI 0.142（路由层） |
| 数据层 | sqlite3 标准库（[db.py](backend/db.py)，含批量导入、schema 迁移、查询缓存） |
| 前端 | HTML / CSS / 原生 JS（无框架）、ECharts 5.5（本地部署，不依赖 CDN） |
| 部署 | Uvicorn 0.54 ASGI 服务器（Windows 友好） |
| 测试 | unittest（FastAPI `TestClient` + 临时数据库隔离） |

## 目录结构

```
TEA/
├── backend/
│   ├── app.py          # FastAPI 路由层：14 个接口、统一筛选/错误处理
│   └── db.py           # 数据层：连接、建表、CSV 导入、索引、进程内查询缓存
├── frontend/
│   ├── index.html      # 大屏页面
│   ├── css/style.css   # 响应式样式
│   └── js/
│       ├── chart.js    # 图表注册表、KPI/洞察加载、联动筛选
│       └── echarts.min.js
├── data/
│   └── bawangchaji_sales.csv  # 原始数据（62,050 行，13 个字段）
├── serve.py            # 生产启动入口（Uvicorn）
├── start.bat           # Windows 一键启动（自动选用 .venv）
├── test.py             # 22 个 unittest 用例
└── requirements.txt
```

## 快速开始

```bash
# 1. 安装依赖（建议虚拟环境）
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

# 2. 启动（任选其一）
python serve.py                    # 推荐：Uvicorn 生产模式，默认对局域网开放
start.bat                          # 或双击一键启动
python backend/app.py              # 直接启动 Uvicorn

# 3. 打开浏览器
#    本机：   http://127.0.0.1:8080
#    局域网： http://<本机局域网IP>:8080   （同一 Wi-Fi，首次需放行 Windows 防火墙）
```

首次启动自动建库并导入 CSV；之后仅在 schema 版本或 CSV 文件 mtime 变化时才重建/重导。
数据库文件 `backend/bawangchaji.db` 为派生文件，可随时删除后重启自动重建。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `TEA_HOST` | `0.0.0.0` | 监听地址；设为 `127.0.0.1` 则仅本机可访问 |
| `TEA_PORT` | `8080` | 端口 |
| `TEA_DEBUG` | `0` | `1` 开调试（绑 0.0.0.0 时强制回退 127.0.0.1） |
| `TEA_DB_PATH` | `backend/bawangchaji.db` | 数据库路径（测试用临时库） |
| `TEA_THREADS` | `8` | 保留兼容，不再使用；Uvicorn 当前单进程运行 |
| `TEA_REQUIRE_AUTH` / `TEA_API_KEY` | 关闭 | 对 `/api/*` 启用 Bearer/API-Key 校验 |

## API 一览

所有分析接口均支持同一组查询参数：
`city, product, category, season, weather, start_date, end_date`（任意组合）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 可视化大屏 |
| GET | `/api/health` | 健康检查（实时查库，不走缓存） |
| GET | `/api/filters` | 筛选项字典（城市/产品/类别/季节/天气） |
| GET | `/api/summary` | KPI 汇总：记录数、总销量、总营收 |
| GET | `/api/insights` | **自动业务洞察**（头部集中度、节假日/活动/天气/减免效应） |
| GET | `/api/monthly` | 月度销量与营收趋势 |
| GET | `/api/product_rank` | 产品销量排名 |
| GET | `/api/category_pie` | 品类占比 |
| GET | `/api/city_rank` | 城市销量排名 |
| GET | `/api/season` | 季节对比 |
| GET | `/api/weather` | 天气对平均销量影响 |
| GET | `/api/campaign` | 营销活动效果（对比无活动基线） |
| GET | `/api/city_product` | 城市 × 产品热力图数据 |
| GET | `/api/holiday` | 节假日 vs 非节假日 |
| GET | `/api/discount` | 减免金额（0/2/3 元）对销量影响 |
| GET | `/api/export` | 按当前筛选导出 CSV |

## 核心数据洞察（接口自动计算）

基于全量数据的真实结论：

- **市场较分散**：销量最高的上海仅占 12.0%，前 3 城合计 34.3% —— 无明显单核依赖
- **爆款**：伯牙绝弦占总销量 10.9%，前 3 产品合计 26.1%
- **品类结构**：原叶鲜奶茶一家独大（57.5%），鲜果茶次之（28.4%）
- **季节节奏**：10 月最旺（474,557 杯），高于月均约 8.2%
- **天气敏感**：晴天平均 96 杯/条，大雨天仅 59 杯/条，相差 62.3%
- **节假日效应显著**：节假日平均销量比非节假日高 35.9%
- **活动 ROI 参考**：新品上市效果最好（+24.6%），满减/会员日次之
- **小额减免有正向作用**：减 3 元比无减免平均高 8.6%

## 工程亮点

1. **分层架构**：[db.py](backend/db.py) 数据层与 [app.py](backend/app.py) 路由层分离，14 个接口复用统一 WHERE 构造器
2. **批量导入 + 容错**：`executemany` 每 1000 行一批提交；坏行逐行跳过并计数，不中断整体导入
3. **schema 版本迁移**：`meta` 表记录 schema_version（当前 v2）与 CSV mtime，结构变更自动 DROP 重建，数据未变跳过导入
4. **索引 + 查询缓存**：6 个高频过滤列建索引；只读聚合走带锁的 LRU 进程内缓存（上限 256 条），重导后自动失效。
   实测 6 个聚合接口平均耗时 **30.2ms → 0.29ms（约 103 倍）**
5. **22 个自动化测试**：接口冒烟、筛选结果与直查数据库比对、导出 CSV 内容校验、空/非法日期边界（400 JSON）、缓存命中与 LRU 淘汰、洞察结构
6. **可分享的筛选状态**：筛选条件同步到 URL query，刷新/转发后状态保留；日期选择限定在数据覆盖的 2025 年
7. **生产就绪**：Uvicorn ASGI 部署、一键 `start.bat`、局域网地址自动探测、可选 API Key 鉴权
8. **失败不白屏**：接口异常在图表卡片内给出错误提示；ECharts 资源本地化

## 运行测试

```bash
.venv\Scripts\python.exe test.py
```

测试使用独立临时数据库（`TEA_DB_PATH` 注入），不污染正式库，当前 22 个用例全部通过。

## 后续可扩展方向

- 数据更新改为定时增量同步（当前为启动时按 mtime 全量重导）
- SQLite 换 PostgreSQL + 连接池，缓存升级为 Redis
- 用户体系与报表订阅（定时邮件/飞书推送）
- 更细的门店维度下钻与同比/环比分析

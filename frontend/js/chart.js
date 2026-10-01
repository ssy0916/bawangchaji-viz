/**
 * 霸王茶姬销量数据分析 - ECharts 图表
 */

const purple = "#7c3aed";
const orange = "#f97316";
const palette = ["#7c3aed", "#f97316", "#06b6d4", "#10b981", "#f43f5e", "#3b82f6"];

// 千分位格式化
function fmt(n) { return n == null ? "--" : Number(n).toLocaleString(); }

// 保留一位小数，返回数字而不是字符串（避免 ECharts 当成类目值）
function round1(n) { return Math.round(Number(n) * 10) / 10; }

// 接口/图表加载失败时在卡片内给出提示，而不是一直空白
function showError(el, message) {
    el.innerHTML = '<div class="chart-error">数据加载失败：' + message + '</div>';
}

function urlWithCurrentQuery(url) {
    const current = new URLSearchParams(window.location.search);
    const baseUrl = new URL(url, window.location.origin);
    const params = new URLSearchParams(baseUrl.search);
    for (const [key, value] of current.entries()) {
        params.set(key, value);
    }
    const stringified = params.toString();
    return stringified ? `${url}?${stringified}` : url;
}

// 复用同一容器上的图表实例，避免每次筛选都重复 init；resize 监听每个容器只绑一次
function getOrCreateChart(el) {
    const existing = echarts.getInstanceByDom(el);
    if (existing) return existing;
    const chart = echarts.init(el);
    window.addEventListener("resize", () => chart.resize());
    return chart;
}

// 统一的“取数据 -> 画图 -> 失败提示”流程
function loadChart(elementId, url, draw) {
    const el = document.getElementById(elementId);
    const requestUrl = urlWithCurrentQuery(url);
    return fetch(requestUrl)
        .then(r => {
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
        })
        .then(data => {
            if (data && data.error) throw new Error(data.message || data.error);
            const chart = getOrCreateChart(el);
            chart.clear();
            draw(chart, data);
        })
        .catch(err => showError(el, err.message));
}

// 已注册图表的最小配置：标题、容器、数据接口、绘制函数
const chartRegistry = [];

function registerChart(title, container, api, draw) {
    chartRegistry.push({ title, container, api, draw });
}

function initDashboard() {
    refreshKpi();
    loadInsights();
    loadAllCharts();
}

function refreshDashboard() {
    const query = buildFilterQuery();
    const queryString = query ? `?${query}` : "";
    const exportUrl = "/api/export" + queryString;
    document.getElementById("exportCsv").href = exportUrl;

    if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", `${window.location.pathname}${queryString}`);
    }

    refreshKpi();
    loadInsights();
    loadAllCharts();
}

function loadInsights() {
    const grid = document.getElementById("insightsGrid");
    fetch(urlWithCurrentQuery("/api/insights"))
        .then(r => {
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
        })
        .then(d => {
            if (!d.insights || d.insights.length === 0) {
                grid.textContent = "当前筛选条件下暂无数据";
                return;
            }
            grid.innerHTML = "";
            d.insights.forEach(item => {
                const card = document.createElement("div");
                card.className = "insight-card";
                const title = document.createElement("div");
                title.className = "insight-title";
                title.textContent = item.title;
                const metric = document.createElement("div");
                metric.className = "insight-metric";
                metric.textContent = item.metric;
                const detail = document.createElement("div");
                detail.className = "insight-detail";
                detail.textContent = item.detail;
                card.append(title, metric, detail);
                grid.appendChild(card);
            });
        })
        .catch(err => {
            grid.textContent = "洞察加载失败：" + err.message;
        });
}

function loadAllCharts() {
    chartRegistry.forEach(cfg => loadChart(cfg.container, cfg.api, cfg.draw));
}

function buildFilterQuery() {
    const params = new URLSearchParams();
    const city = document.getElementById("cityFilter").value;
    const product = document.getElementById("productFilter").value;
    const category = document.getElementById("categoryFilter").value;
    const season = document.getElementById("seasonFilter").value;
    const weather = document.getElementById("weatherFilter").value;
    const startDate = document.getElementById("startDateFilter").value;
    const endDate = document.getElementById("endDateFilter").value;

    if (city) params.set("city", city);
    if (product) params.set("product", product);
    if (category) params.set("category", category);
    if (season) params.set("season", season);
    if (weather) params.set("weather", weather);
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);

    return params.toString();
}

function refreshKpi() {
    const query = buildFilterQuery();
    fetch("/api/summary" + (query ? "?" + query : ""))
        .then(r => {
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
        })
        .then(d => {
            document.querySelector("#kpi-qty .kpi-value").textContent = fmt(d.total_qty);
            document.querySelector("#kpi-rev .kpi-value").textContent = fmt(d.total_revenue);
            document.querySelector("#kpi-records .kpi-value").textContent = fmt(d.total_records);
        })
        .catch(err => {
            document.querySelectorAll(".kpi-value").forEach(el => { el.textContent = "--"; });
            console.error("KPI 数据加载失败：", err);
        });
}

fetch("/api/filters")
    .then(r => {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
    })
    .then(data => {
        const map = {
            cityFilter: data.cities,
            productFilter: data.products,
            categoryFilter: data.categories,
            seasonFilter: data.seasons,
            weatherFilter: data.weather,
        };
        for (const [id, values] of Object.entries(map)) {
            const el = document.getElementById(id);
            if (!el) continue;
            values.forEach(v => {
                const opt = document.createElement("option");
                opt.value = v;
                opt.textContent = v;
                el.appendChild(opt);
            });
        }

        const params = new URLSearchParams(window.location.search);
        document.getElementById("cityFilter").value = params.get("city") || "";
        document.getElementById("productFilter").value = params.get("product") || "";
        document.getElementById("categoryFilter").value = params.get("category") || "";
        document.getElementById("seasonFilter").value = params.get("season") || "";
        document.getElementById("weatherFilter").value = params.get("weather") || "";
        document.getElementById("startDateFilter").value = params.get("start_date") || "";
        document.getElementById("endDateFilter").value = params.get("end_date") || "";

        const query = buildFilterQuery();
        const exportUrl = "/api/export" + (query ? "?" + query : "");
        document.getElementById("exportCsv").href = exportUrl;
    })
    .catch(err => console.error("过滤器加载失败：", err))
    .finally(() => {
        // 必须等下拉选项填充并回填 URL 筛选后再初始化，否则带参数的分享链接首次打开会丢筛选
        initDashboard();
    });

// -- 月度销量与营收趋势 --
registerChart("月度销量与营收趋势", "chart-monthly", "/api/monthly", (c, d) => {
    c.setOption({
        tooltip: { trigger: "axis" },
        legend: { data: ["销量(杯)", "营收(元)"] },
        xAxis: {
            type: "category",
            data: d.map(r => r.month),
            axisLabel: { rotate: 30 }
        },
        yAxis: [
            { type: "value", name: "销量" },
            { type: "value", name: "营收" }
        ],
        series: [
            { name: "销量(杯)", type: "line", smooth: true, data: d.map(r => r.qty), itemStyle: { color: purple } },
            { name: "营收(元)", type: "bar", yAxisIndex: 1, data: d.map(r => r.revenue), itemStyle: { color: orange } }
        ],
        grid: { left: 60, right: 60, bottom: 50, top: 50 }
    });
});

// -- 产品销量排名 --
registerChart("产品销量排名", "chart-product", "/api/product_rank", (c, d) => {
    c.setOption({
        tooltip: { trigger: "axis" },
        xAxis: { type: "value" },
        yAxis: {
            type: "category",
            // 销量最高的产品显示在最上方
            data: d.map(r => r.product).reverse()
        },
        series: [{
            name: "销量",
            type: "bar",
            data: d.map(r => r.qty).reverse(),
            label: { show: true, position: "right" }
        }],
        grid: { left: 110, right: 60, top: 10, bottom: 20 }
    });
});

// -- 产品类别占比 --
registerChart("产品类别占比", "chart-category", "/api/category_pie", (c, d) => {
    c.setOption({
        tooltip: { trigger: "item", formatter: "{b}: {c}杯 ({d}%)" },
        series: [{
            type: "pie",
            radius: ["40%", "70%"],
            center: ["50%", "50%"],
            data: d.map(r => ({ name: r.category, value: r.qty })),
            label: { formatter: "{b}\n{d}%" }
        }]
    });
});

// -- 城市销量排名（标题是销量，图也画销量） --
registerChart("城市销量排名", "chart-city", "/api/city_rank", (c, d) => {
    c.setOption({
        tooltip: {
            trigger: "axis",
            formatter: params => {
                const p = params[0];
                const row = d[p.dataIndex];
                return `${row.city}<br/>销量：${fmt(row.qty)} 杯<br/>营收：${fmt(row.revenue)} 元`;
            }
        },
        xAxis: { type: "category", data: d.map(r => r.city), axisLabel: { rotate: 35 } },
        yAxis: { type: "value", name: "销量（杯）" },
        series: [{
            name: "销量",
            type: "bar",
            data: d.map(r => r.qty),
            itemStyle: { color: purple },
            barWidth: 24,
            label: { show: true, position: "top", fontSize: 10 }
        }],
        grid: { left: 80, right: 30, top: 30, bottom: 50 }
    });
});

// -- 季节对比 --
registerChart("季节对比", "chart-season", "/api/season", (c, d) => {
    const order = ["春季", "夏季", "秋季", "冬季"];
    d.sort((a, b) => {
        const ia = order.indexOf(a.season);
        const ib = order.indexOf(b.season);
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    });
    c.setOption({
        tooltip: { trigger: "axis" },
        xAxis: { type: "category", data: d.map(r => r.season) },
        yAxis: { type: "value" },
        series: [{
            type: "bar",
            data: d.map((r, i) => ({
                value: r.qty,
                itemStyle: { color: palette[i % palette.length] }
            })),
            barWidth: 40,
            label: { show: true, position: "top", formatter: "{c}杯" }
        }],
        grid: { left: 60, right: 20, bottom: 20, top: 30 }
    });
});

// -- 天气对销量影响 --
registerChart("天气对销量影响", "chart-weather", "/api/weather", (c, d) => {
    c.setOption({
        tooltip: { trigger: "axis" },
        xAxis: { type: "category", data: d.map(r => r.weather) },
        yAxis: { type: "value", name: "平均销量" },
        series: [{
            type: "bar",
            data: d.map((r, i) => ({
                value: round1(r.avg_qty),
                itemStyle: { color: palette[i % palette.length] }
            })),
            barWidth: 40,
            label: { show: true, position: "top", formatter: "{c}杯" }
        }],
        grid: { left: 50, right: 20, bottom: 20, top: 30 }
    });
});

// -- 营销活动效果 --
registerChart("营销活动效果", "chart-campaign", "/api/campaign", (c, d) => {
    c.setOption({
        tooltip: {
            trigger: "axis",
            formatter: params => {
                const row = d[params[0].dataIndex];
                return `${row.activity}<br/>平均销量：${round1(row.avg_qty)} 杯` +
                    `<br/>平均营收：${fmt(round1(row.avg_revenue))} 元` +
                    `<br/>记录数：${fmt(row.record_count)}`;
            }
        },
        legend: { data: ["平均销量(杯)", "平均营收(元)"], bottom: 0 },
        xAxis: { type: "category", data: d.map(r => r.activity) },
        yAxis: [
            { type: "value", name: "平均销量" },
            { type: "value", name: "平均营收" }
        ],
        series: [
            { name: "平均销量(杯)", type: "bar", barWidth: 30, data: d.map(r => round1(r.avg_qty)), itemStyle: { color: purple } },
            { name: "平均营收(元)", type: "bar", yAxisIndex: 1, barWidth: 30, data: d.map(r => round1(r.avg_revenue)), itemStyle: { color: orange } }
        ],
        grid: { left: 60, right: 60, bottom: 50, top: 30 }
    });
});

// -- 城市 x 产品 热力图 --
registerChart("城市 x 产品 热力图", "chart-heatmap", "/api/city_product", (c, d) => {
    // 空数据时 visualMap + 空类目轴会让 ECharts 在 addColorStop 处崩溃，单独给空态
    if (!d.data || d.data.length === 0) {
        c.setOption({
            title: {
                text: "当前筛选条件下暂无数据",
                left: "center",
                top: "center",
                textStyle: { color: "#9ca3af", fontSize: 14, fontWeight: "normal" }
            }
        });
        return;
    }
    const max = Math.max(...d.data.map(v => v[2])) || 100;
    c.setOption({
        tooltip: {
            position: "top",
            formatter: p => `${d.cities[p.data[1]]} - ${d.products[p.data[0]]}：${p.data[2]}杯`
        },
        xAxis: {
            type: "category",
            data: d.products,
            axisLabel: { rotate: 45 }
        },
        yAxis: {
            type: "category",
            data: d.cities,
            splitArea: { show: true }
        },
        visualMap: {
            min: 0,
            max: max,
            calculable: true,
            orient: "horizontal",
            left: "center",
            bottom: 0,
            inRange: { color: ["#f3e8ff", purple, "#3b0764"] }
        },
        series: [{
            type: "heatmap",
            data: d.data,
            label: { show: true, fontSize: 10 },
            emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0, 0, 0, 0.5)" } }
        }],
        grid: { left: 80, right: 20, bottom: 60, top: 10 }
    });
});

// -- 节假日 vs 非节假日 --
registerChart("节假日 vs 非节假日", "chart-holiday", "/api/holiday", (c, d) => {
    c.setOption({
        tooltip: { trigger: "axis" },
        legend: { data: ["平均销量", "平均营收"], bottom: 0 },
        xAxis: {
            type: "category",
            data: d.map(r => (r.is_holiday === "1" || r.is_holiday === "是") ? "节假日" : "非节假日")
        },
        yAxis: [
            { type: "value", name: "平均销量" },
            { type: "value", name: "平均营收" }
        ],
        series: [
            { name: "平均销量", type: "bar", data: d.map(r => round1(r.avg_qty)) },
            { name: "平均营收", type: "bar", yAxisIndex: 1, data: d.map(r => round1(r.avg_revenue)) }
        ],
        grid: { left: 60, right: 60, bottom: 40, top: 20 }
    });
});

// -- 折扣（减免金额）对销量影响 --
registerChart("折扣对销量影响", "chart-discount", "/api/discount", (c, d) => {
    c.setOption({
        tooltip: { trigger: "axis" },
        xAxis: {
            type: "category",
            name: "减免金额",
            data: d.map(r => Number(r.discount) === 0 ? "无折扣" : `减 ${r.discount} 元`)
        },
        yAxis: { type: "value", name: "平均销量（杯）" },
        series: [{
            type: "bar",
            data: d.map((r, i) => ({
                value: round1(r.avg_qty),
                itemStyle: { color: palette[i % palette.length] }
            })),
            barWidth: 40,
            label: { show: true, position: "top", formatter: "{c}杯" }
        }],
        grid: { left: 60, right: 20, bottom: 40, top: 30 }
    });
});

// 事件绑定可立即执行；首屏 initDashboard() 在上方 /api/filters 回填完成后触发
document.getElementById("applyFilter").addEventListener("click", refreshDashboard);

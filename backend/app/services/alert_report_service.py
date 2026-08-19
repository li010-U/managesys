# -*- coding: utf-8 -*-
"""偶发故障-环境关联可视化报表生成。

基于 EnvWeatherService.correlation_report 的数据，生成一个可独立打开的
HTML 报表（内嵌 Chart.js CDN，绘制逐小时分布、天气分布、环境区间分布），
同时以 JSON 形式返回结构化结果供 API/前端消费。
"""
from __future__ import annotations

import json
from typing import Any, Dict

from app.services.environment_service import EnvWeatherService


class AlertCorrelationReportService:
    def __init__(self, db):
        self.db = db

    async def build(self, days: int | None = None) -> Dict[str, Any]:
        env = EnvWeatherService(self.db)
        data = await env.correlation_report(days=days)
        return data

    def render_html(self, data: Dict[str, Any]) -> str:
        hour = data.get("by_hour", [])
        weather = data.get("by_weather", [])
        buckets = data.get("by_env_bucket", {})
        summary = data.get("summary", {})

        hour_labels = [r["hour"] for r in hour]
        hour_counts = [r["count"] for r in hour]
        weather_labels = [r["weather"] for r in weather]
        weather_counts = [r["count"] for r in weather]
        weather_colors = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1", "#ff9da7"]

        t_buckets = buckets.get("temperature", [])
        h_buckets = buckets.get("humidity", [])
        w_buckets = buckets.get("windspeed", [])

        def bar(labels, counts, color):
            return {
                "type": "bar",
                "data": {"labels": labels, "datasets": [{"label": "偶发故障次数", "data": counts, "backgroundColor": color}]},
            }

        # 饼图用一次性颜色
        bar_hour = bar(hour_labels, hour_counts, "#4e79a7")
        bar_temp = bar([r["bucket"] for r in t_buckets], [r["count"] for r in t_buckets], "#f28e2b")
        bar_hum = bar([r["bucket"] for r in h_buckets], [r["count"] for r in h_buckets], "#59a14f")
        bar_wind = bar([r["bucket"] for r in w_buckets], [r["count"] for r in w_buckets], "#76b7b2")
        pie_weather = {
            "type": "pie",
            "data": {
                "labels": weather_labels,
                "datasets": [{"data": weather_counts, "backgroundColor": weather_colors[:max(len(weather_counts), 1)]}],
            },
        }

        html_js = f"""
        <!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>偶发故障-环境关联统计报表</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body {{ font-family: "Microsoft YaHei", sans-serif; margin: 24px; background: #f5f6fa; color:#2d3e50; }}
  h1 {{ font-size: 22px; }}
  .summary {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0 24px; }}
  .card {{ background:#fff; border-radius: 10px; padding: 16px 20px; box-shadow:0 2px 8px rgba(0,0,0,.06); flex:1; min-width:140px; }}
  .card .num {{ font-size: 28px; font-weight: 700; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .panel {{ background:#fff; border-radius: 10px; padding: 16px 20px; box-shadow:0 2px 8px rgba(0,0,0,.06); }}
  .panel h3 {{ margin-top: 0; }}
  canvas {{ max-height: 320px; }}
</style>
</head>
<body>
<h1>偶发故障 - 环境关联统计报表</h1>
<div class="summary">
  <div class="card">偶发故障总数<div class="num">{summary.get('count', 0)}</div></div>
  <div class="card">平均时长<div class="num">{summary.get('avg_duration_seconds', 0)}s</div></div>
  <div class="card">最长时长<div class="num">{summary.get('max_duration_seconds', 0)}s</div></div>
  <div class="card">累计时长<div class="num">{summary.get('total_duration_seconds', 0)}s</div></div>
</div>
<div class="grid">
  <div class="panel"><h3>逐小时分布</h3><canvas id="ch1"></canvas></div>
  <div class="panel"><h3>天气类型分布</h3><canvas id="ch2"></canvas></div>
  <div class="panel"><h3>温度区间分布</h3><canvas id="ch3"></canvas></div>
  <div class="panel"><h3>湿度区间分布</h3><canvas id="ch4"></canvas></div>
  <div class="panel"><h3>风速区间分布</h3><canvas id="ch5"></canvas></div>
</div>
<script>
const cfg = {{
  ch1: {json.dumps(bar_hour)},
  ch2: {json.dumps(pie_weather)},
  ch3: {json.dumps(bar_temp)},
  ch4: {json.dumps(bar_hum)},
  ch5: {json.dumps(bar_wind)},
}};
for (const [id, c] of Object.entries(cfg)) {{
  new Chart(document.getElementById(id), c);
}}
</script>
</body>
</html>
"""
        return html_js

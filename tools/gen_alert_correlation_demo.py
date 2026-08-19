# -*- coding: utf-8 -*-
"""生成偶发故障-环境关联统计的演示 HTML 报表（含可视化）。

在独立临时 SQLite 中构造示例数据，不触碰线上数据库。
产出 reports/alert_correlation_demo.html。
"""
import asyncio, os, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

TMP_DB = tempfile.mktemp(prefix="alert_corr_demo_", suffix=".db")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + TMP_DB
os.environ["DATABASE_URL_SYNC"] = "sqlite:///" + TMP_DB
os.environ["ALERT_LIFECYCLE_TASK_ENABLED"] = "false"
os.environ["SECRET_KEY"] = "demo-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz-ABCDEFGHIJ"


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.db.base import Base
    import app.models
    from app.models.env_weather import TransientFailureEvent
    from app.services.environment_service import EnvWeatherService
    from app.services.alert_report_service import AlertCorrelationReportService
    from app.db.retry import with_commit_retry

    engine = create_async_engine("sqlite+aiosqlite:///" + TMP_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        env = EnvWeatherService(db)
        for t, h, w, ws in [(33.0, 72.0, "多云", 6.5), (20.0, 45.0, "晴", 2.0),
                            (28.0, 78.0, "雨", 9.0), (16.0, 40.0, "晴", 1.5)]:
            await env.record(temperature=t, humidity=h, weather=w, windspeed=ws, location_name="主机房")

        specs = [
            ("雨", 33.0, 78.0, 9.0, 3, 40), ("雨", 32.0, 80.0, 8.0, 5, 60),
            ("多云", 30.0, 70.0, 6.0, 9, 30), ("多云", 31.0, 68.0, 7.0, 10, 45),
            ("晴", 24.0, 48.0, 2.0, 12, 25), ("晴", 23.0, 45.0, 2.5, 13, 20),
            ("雨", 29.0, 82.0, 10.0, 15, 120), ("雨", 30.0, 79.0, 9.5, 16, 90),
            ("晴", 22.0, 44.0, 1.8, 18, 18), ("阴", 26.0, 60.0, 4.0, 20, 35),
            ("阴", 27.0, 62.0, 5.0, 21, 42), ("雨", 28.0, 85.0, 12.0, 23, 150),
        ]
        events = []
        base = __import__("datetime").datetime.now()
        for i, (w, t, h, ws, hh, dur) in enumerate(specs):
            started = base.replace(hour=hh, minute=0, second=0, microsecond=0)
            events.append(TransientFailureEvent(
                alert_id=i + 1, target_type="device", target_id=f"demo-{i+1}",
                title="短时抖动" if dur < 60 else "闪断", metric="temperature",
                started_at=started, recovered_at=started + __import__("datetime").timedelta(seconds=dur),
                duration_seconds=dur, env_weather=w, env_temperature=t,
                env_humidity=h, env_windspeed=ws, location_name="主机房",
            ))
        db.add_all(events)
        await with_commit_retry(db.commit)

        rpt = AlertCorrelationReportService(db)
        data = await rpt.build(days=7)
        html = rpt.render_html(data)

        out_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "alert_correlation_demo.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print("generated:", out_path)
        print("summary:", data["summary"])
        await engine.dispose()

    try:
        if os.path.exists(TMP_DB):
            os.remove(TMP_DB)
    except PermissionError:
        pass


asyncio.run(main())

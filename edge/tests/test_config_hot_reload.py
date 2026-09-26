"""EdgePipeline.apply_remote_config 热更新逻辑测试。"""

from edge.visual_recognition_edge.pipeline import EdgePipeline


def _build_pipeline() -> EdgePipeline:
    """构造一个轻量级 pipeline，跳过真实模型加载。"""
    return EdgePipeline(
        camera_id="cam-x",
        area_id="area-x",
        model_path="",
        api_base_url="http://localhost",
        area_polygon=[[0, 0], [1, 0], [1, 1], [0, 1]],
        api_key="x",
        stay_threshold_seconds=300,
        high_risk_seconds=600,
    )


def test_apply_remote_config_updates_thresholds():
    pipeline = _build_pipeline()
    payload = {
        "revision": 42,
        "stay_threshold_seconds": 100,
        "high_risk_seconds": 250,
        "person_loitering_seconds": 60,
    }
    applied = pipeline.apply_remote_config(payload)
    assert set(applied) == {"stay_threshold_seconds", "high_risk_seconds", "person_loitering_seconds"}
    assert pipeline.stay_threshold_seconds == 100
    assert pipeline.high_risk_seconds == 250
    assert pipeline.person_loitering_seconds == 60


def test_apply_remote_config_skips_same_revision():
    pipeline = _build_pipeline()
    payload = {"revision": 7, "stay_threshold_seconds": 200}
    first = pipeline.apply_remote_config(payload)
    assert "stay_threshold_seconds" in first
    second = pipeline.apply_remote_config(payload)
    assert second == []  # revision 相同，不重复应用


def test_apply_remote_config_ignores_unknown_fields():
    pipeline = _build_pipeline()
    payload = {"revision": 1, "bogus_field": 999}
    applied = pipeline.apply_remote_config(payload)
    assert applied == []
import sys


def test_app_db_legacy_exports_exist():
    from app.db import Generation, OnlineMetrics, XHSNote, XHSMetrics

    assert Generation is not None
    assert OnlineMetrics is not None
    assert XHSNote is not None
    assert XHSMetrics is not None


def test_ml_package_is_lazy_loaded():
    import app.ml as ml_pkg

    assert "app.ml.services.training_service" not in sys.modules
    # 访问轻量 schema 不应触发 training_service
    assert getattr(ml_pkg, "GenerationTrace") is not None
    assert "app.ml.services.training_service" not in sys.modules


def test_ml_rl_package_is_lazy_loaded():
    import app.ml.rl as rl_pkg

    assert "app.ml.rl.online_metrics_collector" not in sys.modules
    assert getattr(rl_pkg, "ThompsonSamplingSelector") is not None
    assert "app.ml.rl.online_metrics_collector" not in sys.modules

import datetime as dt

from quantalgo.data import OHLCV_COLUMNS, DataLoader


def test_synthetic_is_deterministic():
    a = DataLoader("MES").synthetic("2026-02-02", "2026-02-06", "5m", seed=11)
    b = DataLoader("MES").synthetic("2026-02-02", "2026-02-06", "5m", seed=11)
    assert a.equals(b)


def test_synthetic_schema_and_rth_bounds():
    df = DataLoader("MES").synthetic("2026-02-02", "2026-02-06", "5m", seed=1)
    assert list(df.columns) == OHLCV_COLUMNS
    assert not df.empty
    # all bars inside Regular Trading Hours and on weekdays
    assert (df.index.time >= dt.time(9, 30)).all()
    assert (df.index.time < dt.time(16, 0)).all()
    assert set(df.index.dayofweek) <= {0, 1, 2, 3, 4}


def test_ohlc_relationships_hold():
    df = DataLoader("NQ").synthetic("2026-02-02", "2026-02-04", "5m", seed=3)
    assert (df["high"] >= df["low"]).all()
    assert (df["high"] >= df["open"]).all()
    assert (df["high"] >= df["close"]).all()
    assert (df["low"] <= df["open"]).all()
    assert (df["low"] <= df["close"]).all()

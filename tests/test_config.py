
import pytest

from quantalgo.config import SYMBOLS, ChallengeRules, Settings, get_settings


def test_default_settings():
    s = Settings()
    assert s.symbol == "MES"
    assert s.symbol_spec.point_value == 5.0
    assert isinstance(s.challenge, ChallengeRules)


def test_with_symbol_switches_spec():
    s = Settings().with_symbol("NQ")
    assert s.symbol == "NQ"
    assert s.symbol_spec.point_value == 20.0


def test_with_symbol_rejects_unknown():
    with pytest.raises(ValueError):
        Settings().with_symbol("DOGE")


def test_all_symbols_have_positive_point_value():
    assert SYMBOLS
    for spec in SYMBOLS.values():
        assert spec.point_value > 0
        assert spec.tick_size > 0


def test_env_override(monkeypatch):
    monkeypatch.setenv("QA_SYMBOL", "ES")
    monkeypatch.setenv("QA_INITIAL_CAPITAL", "150000")
    get_settings.cache_clear()
    s = get_settings()
    assert s.symbol == "ES"
    assert s.challenge.initial_capital == 150_000.0
    get_settings.cache_clear()

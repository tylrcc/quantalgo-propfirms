from quantalgo.config import SYMBOLS
from quantalgo.execution import PaperBroker


def test_paper_broker_round_trip_pnl():
    spec = SYMBOLS["MES"]  # $5 / point
    broker = PaperBroker(spec, starting_cash=50_000.0)

    broker.market_order("MES", "BUY", 2, price=5000.0)
    assert broker.position("MES").quantity == 2

    broker.market_order("MES", "SELL", 2, price=5010.0)  # +10 pts * $5 * 2 = $100
    assert broker.position("MES").is_flat
    assert round(broker.realised_pnl, 2) == 100.0


def test_paper_broker_flatten():
    spec = SYMBOLS["MES"]
    broker = PaperBroker(spec)
    broker.market_order("MES", "SELL", 1, price=5000.0)  # short
    fill = broker.flatten("MES", price=4990.0)  # buy to cover, +10 pts
    assert fill is not None and fill.side == "BUY"
    assert broker.position("MES").is_flat
    assert round(broker.realised_pnl, 2) == 50.0


def test_paper_broker_rejects_bad_quantity():
    broker = PaperBroker(SYMBOLS["MES"])
    try:
        broker.market_order("MES", "BUY", 0, price=5000.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-positive quantity")

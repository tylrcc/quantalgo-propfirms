"""Human-friendly reporting: metric tables and optional matplotlib charts.

Plotting imports matplotlib lazily and uses the non-interactive ``Agg`` backend so the
library never requires a display and the import cost is only paid when a chart is asked
for.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path


def format_metrics(title: str, metrics: Mapping[str, float]) -> str:
    """Render a metrics mapping as an aligned, boxed text table."""

    rows = [(_label(k), _value(k, v)) for k, v in metrics.items()]
    width = max((len(k) for k, _ in rows), default=10)
    line = "─" * (width + 22)
    out = [line, f" {title}", line]
    out += [f" {k.ljust(width)}   {v:>16}" for k, v in rows]
    out.append(line)
    return "\n".join(out)


def equity_curve_plot(curve: list[tuple[str, float]], path: str | Path, initial: float) -> Path:
    """Save an equity-curve PNG. Returns the written path."""

    plt = _mpl()
    xs = list(range(len(curve)))
    ys = [e for _, e in curve]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(xs, ys, color="#16a34a", linewidth=1.6)
    ax.axhline(initial, color="gray", linestyle="--", linewidth=1, label="Start")
    ax.set_title("Equity Curve")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Equity ($)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out = Path(path)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def montecarlo_plot(final_pnls, metrics: dict[str, float], path: str | Path) -> Path:
    """Save a histogram of simulated final P&L outcomes."""

    plt = _mpl()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.hist(final_pnls, bins=50, color="#2563eb", alpha=0.8)
    ax.axvline(0, color="gray", linestyle="--", linewidth=1)
    ax.set_title(f"Monte-Carlo Final P&L  •  pass rate {metrics.get('pass_rate', 0):.1f}%")
    ax.set_xlabel("Final P&L ($)")
    ax.set_ylabel("Frequency")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = Path(path)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# --------------------------------------------------------------------- helpers
def _mpl():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


_PERCENT_KEYS = {"win_rate", "total_return_pct", "pass_rate", "fail_rate", "timeout_rate"}
_DOLLAR_KEYS = {
    "final_equity", "max_drawdown", "avg_win", "avg_loss", "best_trade",
    "worst_trade", "expected_value", "p05_pnl", "p95_pnl",
}


def _label(key: str) -> str:
    return key.replace("_", " ").title()


def _value(key: str, value: float) -> str:
    if key in _PERCENT_KEYS:
        return f"{value:.2f}%"
    if key in _DOLLAR_KEYS:
        return f"${value:,.2f}"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value}"

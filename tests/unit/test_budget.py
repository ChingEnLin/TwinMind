import pytest

from twin_mind.api.budget import BudgetExceeded, BudgetTracker, compute_cost


def test_compute_cost_breaks_down_buckets():
    cost = compute_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )
    # 1.00 input + 5.00 output + 1.25 cache_w + 0.10 cache_r
    assert abs(cost - (1.00 + 5.00 + 1.25 + 0.10)) < 1e-9


def test_budget_tracker_trips():
    b = BudgetTracker(daily_cap_usd=0.01)
    b.check()
    b.record(input_tokens=1_000_000, output_tokens=1_000_000)
    with pytest.raises(BudgetExceeded):
        b.check()

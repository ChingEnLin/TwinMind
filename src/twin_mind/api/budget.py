from datetime import UTC, datetime, timedelta

from twin_mind.config import settings


class BudgetExceeded(Exception):
    def __init__(self, remaining_seconds: int) -> None:
        super().__init__("daily budget exceeded")
        self.remaining_seconds = remaining_seconds


def _next_utc_midnight(now: datetime) -> datetime:
    tomorrow = (now + timedelta(days=1)).date()
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=UTC)


def compute_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> float:
    # input_tokens from Anthropic excludes cached reads/writes — they are reported separately.
    inp = input_tokens / 1_000_000 * settings.PRICE_INPUT_PER_MTOK
    out = output_tokens / 1_000_000 * settings.PRICE_OUTPUT_PER_MTOK
    cw = cache_creation_input_tokens / 1_000_000 * settings.PRICE_CACHE_WRITE_PER_MTOK
    cr = cache_read_input_tokens / 1_000_000 * settings.PRICE_CACHE_READ_PER_MTOK
    return inp + out + cw + cr


class BudgetTracker:
    def __init__(self, daily_cap_usd: float) -> None:
        self.daily_cap_usd = daily_cap_usd
        self._spent_today_usd = 0.0
        self._reset_at = _next_utc_midnight(datetime.now(UTC))

    def _maybe_reset(self) -> None:
        now = datetime.now(UTC)
        if now >= self._reset_at:
            self._spent_today_usd = 0.0
            self._reset_at = _next_utc_midnight(now)

    def check(self) -> None:
        self._maybe_reset()
        if self._spent_today_usd >= self.daily_cap_usd:
            remaining = max(int((self._reset_at - datetime.now(UTC)).total_seconds()), 1)
            raise BudgetExceeded(remaining_seconds=remaining)

    def record(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
    ) -> float:
        cost = compute_cost(
            input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens
        )
        self._spent_today_usd += cost
        return cost

    @property
    def spent_today_usd(self) -> float:
        return self._spent_today_usd


budget = BudgetTracker(settings.DAILY_BUDGET_USD)

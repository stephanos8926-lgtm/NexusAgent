"""LLM Budget Guard — hard spend caps with immediate circuit breaker.

Provides budget-aware LLM call protection:
- Tracks token spend per day/month per provider
- Trips circuit breaker immediately on RESOURCE_EXHAUSTED (quota/spend cap)
- Refuses new tasks when budget exceeded
- Alerts at configurable thresholds (50%/80%/95%)

Usage::

    from nexusagent.infrastructure.utils.budget import LLMBudgetGuard

    guard = LLMBudgetGuard(
        daily_budget_usd=10.0,
        monthly_budget_usd=100.0,
        alert_thresholds=[0.5, 0.8, 0.95],
    )

    # Check before submitting task
    if not guard.can_submit_task():
        raise BudgetExceededError("Daily budget exceeded")

    # Record LLM call
    guard.record_call(
        provider="gemini",
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.002,
    )
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


class BudgetState(Enum):
    """Budget guard states."""

    OK = "ok"  # Within budget
    WARNING = "warning"  # Approaching threshold
    EXCEEDED = "exceeded"  # Budget exceeded
    QUOTA_EXHAUSTED = "quota_exhausted"  # Hard quota hit (RESOURCE_EXHAUSTED)


@dataclass
class SpendRecord:
    """Single LLM call spend record."""

    timestamp: float
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    task_id: str | None = None


@dataclass
class BudgetWindow:
    """Spending window (daily or monthly)."""

    window_type: Literal["daily", "monthly"]
    budget_usd: float
    spent_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    call_count: int = 0
    last_alert_threshold: float = 0.0  # Last threshold that triggered alert
    quota_exhausted: bool = False  # True if hit hard quota limit
    quota_exhausted_at: float | None = None


@dataclass
class LLMBudgetGuardState:
    """Persistent state for budget guard."""

    daily: BudgetWindow = field(default_factory=lambda: BudgetWindow("daily", 0.0))
    monthly: BudgetWindow = field(default_factory=lambda: BudgetWindow("monthly", 0.0))
    last_reset_daily: float = 0.0
    last_reset_monthly: float = 0.0


class BudgetExceededError(Exception):
    """Raised when budget is exceeded and task submission is rejected."""

    def __init__(
        self,
        message: str,
        budget_type: Literal["daily", "monthly"],
        spent: float,
        budget: float,
    ):
        self.budget_type = budget_type
        self.spent = spent
        self.budget = budget
        super().__init__(message)


class LLMBudgetGuard:
    """Budget guard with spend tracking and circuit breaker integration.

    Protects against runaway LLM costs by:
    1. Tracking spend per day/month
    2. Tripping on RESOURCE_EXHAUSTED errors (hard quota)
    3. Rejecting new tasks when budget exceeded
    4. Alerting at configurable thresholds

    State persisted to ~/.nexusagent/budget_state.json for crash recovery.
    """

    STATE_FILE = Path.home() / ".nexusagent" / "budget_state.json"

    def __init__(
        self,
        daily_budget_usd: float | None = None,
        monthly_budget_usd: float | None = None,
        alert_thresholds: list[float] | None = None,
        quota_cooldown_seconds: float = 3600.0,  # 1 hour cooldown after quota hit
        enabled: bool = True,
    ):
        """Initialize budget guard.

        Args:
            daily_budget_usd: Daily spend limit (USD). Set 0 to disable daily check.
            monthly_budget_usd: Monthly spend limit (USD). Set 0 to disable monthly check.
            alert_thresholds: List of thresholds (0.0-1.0) to trigger alerts.
                Default: [0.5, 0.8, 0.95] for 50%/80%/95% warnings.
            quota_cooldown_seconds: Seconds to wait after quota exhaustion before
                allowing calls again. Default: 1 hour.
            enabled: Whether budget guard is enabled. If False, all checks pass.
        """
        # Use config values, fallback to sensible defaults for new users
        # Defaults are conservative (1M daily / 10M monthly tokens ≈ $10/$100 for gemini-2.5-flash)
        self.daily_budget_usd = daily_budget_usd if daily_budget_usd is not None else 10.0
        self.monthly_budget_usd = monthly_budget_usd if monthly_budget_usd is not None else 100.0
        self.alert_thresholds = sorted(alert_thresholds or [0.5, 0.8, 0.95])
        self.quota_cooldown_seconds = quota_cooldown_seconds
        self.enabled = enabled

        self._state = LLMBudgetGuardState()
        self._lock = asyncio.Lock()
        self._recent_calls: list[SpendRecord] = []  # In-memory recent calls

        # Load persisted state
        self._load_state()

        # Initialize windows if budgets set
        if self.daily_budget_usd > 0:
            self._state.daily.budget_usd = self.daily_budget_usd
        if self.monthly_budget_usd > 0:
            self._state.monthly.budget_usd = self.monthly_budget_usd

        # Check/reset windows on startup
        self._check_window_reset()

    @property
    def state(self) -> BudgetState:
        """Return current budget state."""
        if self._state.monthly.quota_exhausted or self._state.daily.quota_exhausted:
            # Check if cooldown has elapsed
            now = time.time()
            for window in [self._state.daily, self._state.monthly]:
                if window.quota_exhausted and window.quota_exhausted_at:
                    if now - window.quota_exhausted_at < self.quota_cooldown_seconds:
                        return BudgetState.QUOTA_EXHAUSTED
                    else:
                        # Cooldown elapsed, reset
                        window.quota_exhausted = False
                        window.quota_exhausted_at = None

        if (
            self.daily_budget_usd > 0
            and self._state.daily.spent_usd >= self.daily_budget_usd
        ):
            return BudgetState.EXCEEDED
        if (
            self.monthly_budget_usd > 0
            and self._state.monthly.spent_usd >= self.monthly_budget_usd
        ):
            return BudgetState.EXCEEDED

        # Check thresholds
        for threshold in reversed(self.alert_thresholds):
            if self._state.daily.budget_usd > 0:
                ratio = self._state.daily.spent_usd / self._state.daily.budget_usd
                if ratio >= threshold:
                    return BudgetState.WARNING
            if self._state.monthly.budget_usd > 0:
                ratio = self._state.monthly.spent_usd / self._state.monthly.budget_usd
                if ratio >= threshold:
                    return BudgetState.WARNING

        return BudgetState.OK

    def _check_window_reset(self) -> None:
        """Reset daily/monthly windows if time has elapsed."""
        now = time.time()
        now_dt = datetime.now(UTC)

        # Daily reset (at midnight UTC)
        last_midnight = (now_dt - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        last_midnight_ts = last_midnight.timestamp()
        if self._state.last_reset_daily < last_midnight_ts:
            logger.info("Resetting daily budget window")
            self._state.daily.spent_usd = 0.0
            self._state.daily.input_tokens = 0
            self._state.daily.output_tokens = 0
            self._state.daily.call_count = 0
            self._state.daily.last_alert_threshold = 0.0
            # Don't reset quota_exhausted — that persists through day boundary
            self._state.last_reset_daily = now

        # Monthly reset (1st of month UTC)
        first_of_month = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if self._state.last_reset_monthly < first_of_month.timestamp():
            logger.info("Resetting monthly budget window")
            self._state.monthly.spent_usd = 0.0
            self._state.monthly.input_tokens = 0
            self._state.monthly.output_tokens = 0
            self._state.monthly.call_count = 0
            self._state.monthly.last_alert_threshold = 0.0
            # Don't reset quota_exhausted
            self._state.last_reset_monthly = now

    def _load_state(self) -> None:
        """Load persisted state from disk."""
        if not self.STATE_FILE.exists():
            return
        try:
            data = json.loads(self.STATE_FILE.read_text())
            self._state.daily = BudgetWindow(**data.get("daily", {}))
            self._state.monthly = BudgetWindow(**data.get("monthly", {}))
            self._state.last_reset_daily = data.get("last_reset_daily", 0.0)
            self._state.last_reset_monthly = data.get("last_reset_monthly", 0.0)
            logger.debug(f"Loaded budget state from {self.STATE_FILE}")
        except Exception as e:
            logger.warning(f"Failed to load budget state: {e}")

    def _save_state(self) -> None:
        """Persist state to disk."""
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "daily": {
                    "window_type": self._state.daily.window_type,
                    "budget_usd": self._state.daily.budget_usd,
                    "spent_usd": self._state.daily.spent_usd,
                    "input_tokens": self._state.daily.input_tokens,
                    "output_tokens": self._state.daily.output_tokens,
                    "call_count": self._state.daily.call_count,
                    "last_alert_threshold": self._state.daily.last_alert_threshold,
                    "quota_exhausted": self._state.daily.quota_exhausted,
                    "quota_exhausted_at": self._state.daily.quota_exhausted_at,
                },
                "monthly": {
                    "window_type": self._state.monthly.window_type,
                    "budget_usd": self._state.monthly.budget_usd,
                    "spent_usd": self._state.monthly.spent_usd,
                    "input_tokens": self._state.monthly.input_tokens,
                    "output_tokens": self._state.monthly.output_tokens,
                    "call_count": self._state.monthly.call_count,
                    "last_alert_threshold": self._state.monthly.last_alert_threshold,
                    "quota_exhausted": self._state.monthly.quota_exhausted,
                    "quota_exhausted_at": self._state.monthly.quota_exhausted_at,
                },
                "last_reset_daily": self._state.last_reset_daily,
                "last_reset_monthly": self._state.last_reset_monthly,
            }
            self.STATE_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save budget state: {e}")

    async def can_submit_task(self) -> tuple[bool, str | None]:
        """Check if a new task can be submitted (budget allows).

        Returns:
            Tuple of (allowed, reason). If allowed is False, reason explains why.
        """
        if not self.enabled:
            return True, None

        async with self._lock:
            self._check_window_reset()

            # Check quota exhaustion (hard block)
            for window_name, window in [
                ("daily", self._state.daily),
                ("monthly", self._state.monthly),
            ]:
                if window.quota_exhausted and window.quota_exhausted_at:
                    elapsed = time.time() - window.quota_exhausted_at
                    if elapsed < self.quota_cooldown_seconds:
                        remaining = self.quota_cooldown_seconds - elapsed
                        return (
                            False,
                            f"{window_name.capitalize()} quota exhausted. "
                            f"Cooldown: {remaining:.0f}s remaining",
                        )

            # Check budget limits
            if self.daily_budget_usd > 0:
                if self._state.daily.spent_usd >= self.daily_budget_usd:
                    return (
                        False,
                        f"Daily budget exceeded: ${self._state.daily.spent_usd:.2f} / ${self.daily_budget_usd:.2f}",
                    )

            if self.monthly_budget_usd > 0:
                if self._state.monthly.spent_usd >= self.monthly_budget_usd:
                    return (
                        False,
                        f"Monthly budget exceeded: ${self._state.monthly.spent_usd:.2f} / ${self.monthly_budget_usd:.2f}",
                    )

            return True, None

    async def record_call(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        task_id: str | None = None,
    ) -> None:
        """Record an LLM call and update spend tracking.

        Args:
            provider: LLM provider (e.g., "gemini", "openrouter").
            model: Model name (e.g., "gemini-2.5-flash").
            input_tokens: Input token count.
            output_tokens: Output token count.
            cost_usd: Cost of this call in USD.
            task_id: Optional task ID for tracing.
        """
        async with self._lock:
            self._check_window_reset()

            record = SpendRecord(
                timestamp=time.time(),
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                task_id=task_id,
            )
            self._recent_calls.append(record)

            # Trim recent calls (keep last 1000)
            if len(self._recent_calls) > 1000:
                self._recent_calls = self._recent_calls[-1000:]

            # Update daily window
            self._state.daily.spent_usd += cost_usd
            self._state.daily.input_tokens += input_tokens
            self._state.daily.output_tokens += output_tokens
            self._state.daily.call_count += 1

            # Update monthly window
            self._state.monthly.spent_usd += cost_usd
            self._state.monthly.input_tokens += input_tokens
            self._state.monthly.output_tokens += output_tokens
            self._state.monthly.call_count += 1

            # Check alert thresholds
            for threshold in self.alert_thresholds:
                if threshold > self._state.daily.last_alert_threshold:
                    if self.daily_budget_usd > 0:
                        ratio = self._state.daily.spent_usd / self.daily_budget_usd
                        if ratio >= threshold:
                            self._alert(
                                "daily",
                                threshold,
                                self._state.daily.spent_usd,
                                self.daily_budget_usd,
                            )
                            self._state.daily.last_alert_threshold = threshold

                    if self.monthly_budget_usd > 0:
                        ratio = self._state.monthly.spent_usd / self.monthly_budget_usd
                        if ratio >= threshold:
                            self._alert(
                                "monthly",
                                threshold,
                                self._state.monthly.spent_usd,
                                self.monthly_budget_usd,
                            )
                            self._state.monthly.last_alert_threshold = threshold

            self._save_state()
            logger.debug(
                f"Recorded LLM call: {provider}/{model}, {cost_usd:.4f} USD, "
                f"{input_tokens}+{output_tokens} tokens"
            )

    def _alert(
        self, window_type: str, threshold: float, spent: float, budget: float
    ) -> None:
        """Send budget threshold alert."""
        pct = int(threshold * 100)
        msg = (
            f"🚨 BUDGET ALERT: {window_type.capitalize()} spend at {pct}%\n"
            f"  Spent: ${spent:.2f} / Budget: ${budget:.2f}\n"
            f"  Remaining: ${budget - spent:.2f}"
        )
        logger.warning(msg)
        # TODO: Hook integration for webhook/alerting
        # Could call: run_hook("on_budget_alert", window_type, threshold, spent, budget)

    async def record_quota_exhausted(
        self, window_type: Literal["daily", "monthly"] | None = None
    ) -> None:
        """Record that a quota/spend cap was hit (RESOURCE_EXHAUSTED).

        This trips the circuit breaker and initiates cooldown period.

        Args:
            window_type: Which window hit the quota. If None, marks both.
        """
        async with self._lock:
            now = time.time()
            windows = []
            if window_type is None or window_type == "daily":
                windows.append(("daily", self._state.daily))
            if window_type is None or window_type == "monthly":
                windows.append(("monthly", self._state.monthly))

            for name, window in windows:
                window.quota_exhausted = True
                window.quota_exhausted_at = now
                logger.critical(
                    f"🔴 QUOTA EXHAUSTED: {name} budget. "
                    f"Cooldown: {self.quota_cooldown_seconds}s"
                )

            self._save_state()

    def get_state_summary(self) -> dict:
        """Return human-readable budget state summary."""
        self._check_window_reset()
        return {
            "state": self.state.value,
            "daily": {
                "spent": f"${self._state.daily.spent_usd:.2f}",
                "budget": f"${self._state.daily.budget_usd:.2f}",
                "pct": (
                    f"{(self._state.daily.spent_usd / self._state.daily.budget_usd * 100):.1f}%"
                    if self._state.daily.budget_usd > 0
                    else "N/A"
                ),
                "calls": self._state.daily.call_count,
                "quota_exhausted": self._state.daily.quota_exhausted,
            },
            "monthly": {
                "spent": f"${self._state.monthly.spent_usd:.2f}",
                "budget": f"${self._state.monthly.budget_usd:.2f}",
                "pct": (
                    f"{(self._state.monthly.spent_usd / self._state.monthly.budget_usd * 100):.1f}%"
                    if self._state.monthly.budget_usd > 0
                    else "N/A"
                ),
                "calls": self._state.monthly.call_count,
                "quota_exhausted": self._state.monthly.quota_exhausted,
            },
            "cooldown_remaining_s": self._get_cooldown_remaining(),
        }

    def _get_cooldown_remaining(self) -> float:
        """Get remaining cooldown seconds (0 if not in cooldown)."""
        now = time.time()
        for window in [self._state.daily, self._state.monthly]:
            if window.quota_exhausted and window.quota_exhausted_at:
                elapsed = now - window.quota_exhausted_at
                if elapsed < self.quota_cooldown_seconds:
                    return self.quota_cooldown_seconds - elapsed
        return 0.0


# Module-level singleton
_guard_instance: LLMBudgetGuard | None = None


def create_budget_guard_from_config(config: "ConfigSchema") -> LLMBudgetGuard:
    """Create LLMBudgetGuard from config schema."""
    global _guard_instance
    _guard_instance = LLMBudgetGuard(
        daily_budget_usd=config.budget.daily_budget_usd,
        monthly_budget_usd=config.budget.monthly_budget_usd,
        alert_thresholds=config.budget.alert_thresholds,
        quota_cooldown_seconds=config.budget.quota_cooldown_seconds,
        enabled=config.budget.enabled,
    )
    return _guard_instance


def get_budget_guard() -> LLMBudgetGuard:
    """Get or create the module-level LLMBudgetGuard singleton."""
    global _guard_instance
    if _guard_instance is None:
        from nexusagent.infrastructure.config import settings

        _guard_instance = create_budget_guard_from_config(settings)
    return _guard_instance


def set_budget_guard(instance: LLMBudgetGuard) -> None:
    """Override the module-level LLMBudgetGuard singleton (for testing)."""
    global _guard_instance
    _guard_instance = instance
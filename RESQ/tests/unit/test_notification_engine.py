"""
Unit tests for the notification engine trigger/cooldown logic.
See WORKFLOW.md Phase 12 for the contract these enforce.
"""
from intelligence.notification.notifier import NotificationEngine, NotificationStatus


def test_no_notification_below_threshold():
    engine = NotificationEngine()
    status = engine.evaluate(priority=50, critical_threshold=80,
                              persistence_seconds=10, cooldown_seconds=120, now=0)
    assert status == NotificationStatus.SUPPRESSED_NOT_PERSISTENT


def test_pending_until_persistence_window_elapses():
    engine = NotificationEngine()
    engine.evaluate(priority=90, critical_threshold=80,
                     persistence_seconds=10, cooldown_seconds=120, now=0)
    status = engine.evaluate(priority=90, critical_threshold=80,
                              persistence_seconds=10, cooldown_seconds=120, now=5)
    assert status == NotificationStatus.PENDING


def test_fires_after_persistence_window():
    engine = NotificationEngine()
    engine.evaluate(priority=90, critical_threshold=80,
                     persistence_seconds=10, cooldown_seconds=120, now=0)
    status = engine.evaluate(priority=90, critical_threshold=80,
                              persistence_seconds=10, cooldown_seconds=120, now=11)
    assert status == NotificationStatus.SENT


def test_cooldown_suppresses_repeat_notification():
    engine = NotificationEngine()
    engine.evaluate(priority=90, critical_threshold=80,
                     persistence_seconds=10, cooldown_seconds=120, now=0)
    engine.evaluate(priority=90, critical_threshold=80,
                     persistence_seconds=10, cooldown_seconds=120, now=11)
    engine._last_notified_at = 11  # simulate a completed notify()
    status = engine.evaluate(priority=95, critical_threshold=80,
                              persistence_seconds=10, cooldown_seconds=120, now=20)
    assert status == NotificationStatus.SUPPRESSED_COOLDOWN


def test_brief_spike_that_drops_before_persistence_never_fires():
    """WORKFLOW.md Phase 15 hardening: a brief spike must not notify, even
    much later — dropping below threshold resets the persistence clock."""
    engine = NotificationEngine()
    engine.evaluate(priority=90, critical_threshold=80,
                     persistence_seconds=10, cooldown_seconds=120, now=0)
    mid_spike = engine.evaluate(priority=90, critical_threshold=80,
                                 persistence_seconds=10, cooldown_seconds=120, now=3)
    assert mid_spike == NotificationStatus.PENDING

    dropped = engine.evaluate(priority=50, critical_threshold=80,
                               persistence_seconds=10, cooldown_seconds=120, now=4)
    assert dropped == NotificationStatus.SUPPRESSED_NOT_PERSISTENT

    much_later = engine.evaluate(priority=50, critical_threshold=80,
                                  persistence_seconds=10, cooldown_seconds=120, now=100)
    assert much_later == NotificationStatus.SUPPRESSED_NOT_PERSISTENT


def test_alert_latched_false_before_any_notification():
    engine = NotificationEngine()
    assert engine.is_alert_latched(latch_seconds=10, now=0) is False


def test_alert_latches_true_for_persistence_window_after_firing():
    """Task 1.4: once a real notification fires, the alert stays latched
    active for the configured window even if a later tick's priority dips —
    band/priority themselves are unaffected, this is a separate flag."""
    engine = NotificationEngine()
    engine.evaluate(priority=90, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0)
    engine.evaluate(priority=90, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=11)
    engine.mark_notified(now=11)  # simulates a completed dispatch, same as NotificationDispatcher does

    assert engine.is_alert_latched(latch_seconds=10, now=11) is True
    assert engine.is_alert_latched(latch_seconds=10, now=15) is True  # still within the window
    assert engine.is_alert_latched(latch_seconds=10, now=20.9) is True
    assert engine.is_alert_latched(latch_seconds=10, now=21.1) is False  # window has elapsed

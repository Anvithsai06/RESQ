"""
Unit tests for the Phase 12 notification dispatch layer: recipient
selection from building/emergency_contacts.json, payload construction,
fire-and-forget dispatch, cooldown-override on a new contributor, and
honest failure logging.
"""
import pytest

from intelligence.incident.state import IncidentExit, IncidentState
from intelligence.notification.notifier import (
    EmergencyContact,
    EmergencyContactsDirectory,
    InMemoryNotificationLogger,
    NotificationDispatcher,
    NotificationEngine,
    NotificationResult,
    NotificationStatus,
    build_payloads,
)


def make_incident_state(priority=90.0, contributors=None, affected_zones=None, exits=None, timestamp=0.0):
    return IncidentState(
        timestamp=timestamp, camera_id="CAM-01", priority=priority, band="critical", trend="stable",
        affected_zones=affected_zones or ["DANGER-A"], people=[], hazards=[], exits=exits or [], congestion={},
        contributors=contributors or ["hazard_exposure"], confidence=0.9, uncertainty=False,
        notification=None, timeline=[],
    )


FIRE = EmergencyContact(
    service_id="FIRE-01", service_type="fire", name="City Fire Dept",
    channels=[{"type": "webhook", "target": "https://fire.example/alerts"}],
    notify_for_zone_types=["danger", "obstruction"], priority_rank=1, distance_note="0.4 mi",
)
POLICE = EmergencyContact(
    service_id="POLICE-01", service_type="police", name="City Police",
    channels=[{"type": "email", "target": "dispatch@police.example"}],
    notify_for_zone_types=["danger"], priority_rank=2,
)

ZONE_TYPES = {"DANGER-A": "danger", "OBSTRUCTION-1": "obstruction", "SAFE-OBS": "safe_observation"}


class FakeProvider:
    def __init__(self, result=None, raises=None):
        self.result = result or NotificationResult(status=NotificationStatus.SENT, detail="fake")
        self.raises = raises
        self.sent_payloads = []

    def send(self, payload):
        self.sent_payloads.append(payload)
        if self.raises:
            raise self.raises
        return self.result


def test_emergency_contacts_directory_loads_real_config():
    directory = EmergencyContactsDirectory.from_file("building/emergency_contacts.json")

    service_ids = {c.service_id for c in directory.contacts}
    assert {"FIRE-01", "POLICE-01", "EMS-01"} <= service_ids
    # sorted by priority_rank
    assert [c.priority_rank for c in directory.contacts] == sorted(c.priority_rank for c in directory.contacts)


def test_select_for_zone_types_matches_and_orders_by_priority_rank():
    directory = EmergencyContactsDirectory([POLICE, FIRE])  # deliberately out of rank order

    matches = directory.select_for_zone_types({"danger"})
    assert [c.service_id for c in matches] == ["FIRE-01", "POLICE-01"]  # rank 1 before rank 2

    obstruction_only = directory.select_for_zone_types({"obstruction"})
    assert [c.service_id for c in obstruction_only] == ["FIRE-01"]  # police doesn't cover obstruction

    none_match = directory.select_for_zone_types({"safe_observation"})
    assert none_match == []


def test_build_payloads_mirrors_incident_state_explainability():
    incident = make_incident_state(
        priority=82.0, contributors=["hazard_exposure", "exit_obstruction"], affected_zones=["DANGER-A"],
        exits=[IncidentExit(exit_id="EXIT-B", state="OBSTRUCTED", occupancy=2, persistence_seconds=6.0, evidence_confidence=0.9)],
    )

    payloads = build_payloads(incident, [FIRE], building_id="BLDG-DEMO-01")

    assert len(payloads) == 1
    p = payloads[0]
    assert p.building_id == "BLDG-DEMO-01"
    assert p.camera_id == "CAM-01"
    assert p.priority == 82.0
    assert p.top_contributors == ["hazard_exposure", "exit_obstruction"]
    assert p.affected_zones == ["DANGER-A"]
    assert p.exit_states == {"EXIT-B": "OBSTRUCTED"}
    assert p.confidence == 0.9
    assert p.uncertainty is False
    assert p.recipient_service_id == "FIRE-01"
    assert p.channel_type == "webhook"
    assert p.channel_target == "https://fire.example/alerts"


def test_dispatch_suppressed_not_persistent_below_threshold():
    dispatcher = NotificationDispatcher(NotificationEngine(FakeProvider()), EmergencyContactsDirectory([FIRE]), ZONE_TYPES, "BLDG-DEMO-01")
    incident = make_incident_state(priority=50.0)

    outcome = dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)

    assert outcome.status == NotificationStatus.SUPPRESSED_NOT_PERSISTENT
    assert "below critical threshold" in outcome.reason
    dispatcher.shutdown()


def test_dispatch_pending_reports_remaining_seconds():
    dispatcher = NotificationDispatcher(NotificationEngine(FakeProvider()), EmergencyContactsDirectory([FIRE]), ZONE_TYPES, "BLDG-DEMO-01")
    incident = make_incident_state(priority=90.0)

    dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)
    outcome = dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=4.0)

    assert outcome.status == NotificationStatus.PENDING
    assert "6s more" in outcome.reason
    dispatcher.shutdown()


def test_dispatch_sends_to_matching_recipients_and_logs_success():
    provider = FakeProvider()
    logger = InMemoryNotificationLogger()
    dispatcher = NotificationDispatcher(
        NotificationEngine(provider), EmergencyContactsDirectory([FIRE, POLICE]), ZONE_TYPES, "BLDG-DEMO-01", logger=logger
    )
    incident = make_incident_state(priority=90.0, affected_zones=["DANGER-A"])

    dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)
    outcome = dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=11.0)
    dispatcher.shutdown(wait=True)

    assert outcome.status == NotificationStatus.SENT
    assert {c.service_id for c in outcome.recipients} == {"FIRE-01", "POLICE-01"}
    assert len(logger.entries) == 2
    assert all(result.status == NotificationStatus.SENT for _, result in logger.entries)


def test_dispatch_no_recipient_configured_for_unmatched_zone_type():
    dispatcher = NotificationDispatcher(
        NotificationEngine(FakeProvider()), EmergencyContactsDirectory([FIRE, POLICE]), ZONE_TYPES, "BLDG-DEMO-01"
    )
    incident = make_incident_state(priority=90.0, affected_zones=["SAFE-OBS"])  # not covered by any contact

    dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)
    outcome = dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=11.0)

    assert outcome.status == NotificationStatus.NO_RECIPIENT_CONFIGURED
    dispatcher.shutdown()


def test_dispatch_cooldown_suppresses_repeat_with_same_contributors():
    provider = FakeProvider()
    dispatcher = NotificationDispatcher(NotificationEngine(provider), EmergencyContactsDirectory([FIRE]), ZONE_TYPES, "BLDG-DEMO-01")
    incident = make_incident_state(priority=90.0, contributors=["hazard_exposure"])

    dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)
    first = dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=11.0)
    dispatcher.shutdown(wait=True)
    assert first.status == NotificationStatus.SENT

    repeat = dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=20.0)
    assert repeat.status == NotificationStatus.SUPPRESSED_COOLDOWN
    assert "cooldown" in repeat.reason


def test_dispatch_cooldown_overridden_by_new_distinct_contributor():
    provider = FakeProvider()
    logger = InMemoryNotificationLogger()
    dispatcher = NotificationDispatcher(NotificationEngine(provider), EmergencyContactsDirectory([FIRE]), ZONE_TYPES, "BLDG-DEMO-01", logger=logger)

    first_incident = make_incident_state(priority=90.0, contributors=["hazard_exposure"])
    dispatcher.evaluate_and_dispatch(first_incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)
    first = dispatcher.evaluate_and_dispatch(first_incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=11.0)
    assert first.status == NotificationStatus.SENT

    # Still within the 120s cooldown, but a materially new contributor
    # (exit_obstruction) has appeared alongside the original hazard.
    second_incident = make_incident_state(priority=95.0, contributors=["hazard_exposure", "exit_obstruction"])
    second = dispatcher.evaluate_and_dispatch(second_incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=20.0)
    dispatcher.shutdown(wait=True)

    assert second.status == NotificationStatus.SENT
    assert len(logger.entries) == 2  # one from each of the two SENT dispatches


def test_provider_failure_is_logged_as_failed_not_silently_dropped():
    provider = FakeProvider(raises=ConnectionError("network unreachable"))
    logger = InMemoryNotificationLogger()
    dispatcher = NotificationDispatcher(NotificationEngine(provider), EmergencyContactsDirectory([FIRE]), ZONE_TYPES, "BLDG-DEMO-01", logger=logger)
    incident = make_incident_state(priority=90.0)

    dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)
    outcome = dispatcher.evaluate_and_dispatch(incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=11.0)
    dispatcher.shutdown(wait=True)

    assert outcome.status == NotificationStatus.SENT  # dispatch was initiated...
    assert len(logger.entries) == 1
    _, result = logger.entries[0]
    assert result.status == NotificationStatus.FAILED  # ...but the actual send failed, and that's what's logged
    assert "network unreachable" in result.detail


def test_dispatch_does_not_fire_on_brief_spike_that_drops_before_persistence():
    """WORKFLOW.md Phase 15 hardening, exercised through the full dispatch
    path (recipient selection, cooldown-override logic) rather than just
    the raw state machine."""
    provider = FakeProvider()
    logger = InMemoryNotificationLogger()
    dispatcher = NotificationDispatcher(NotificationEngine(provider), EmergencyContactsDirectory([FIRE]), ZONE_TYPES, "BLDG-DEMO-01", logger=logger)

    spike = make_incident_state(priority=90.0)
    dispatcher.evaluate_and_dispatch(spike, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)
    mid = dispatcher.evaluate_and_dispatch(spike, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=3.0)
    assert mid.status == NotificationStatus.PENDING

    dropped_incident = make_incident_state(priority=50.0)
    dropped = dispatcher.evaluate_and_dispatch(dropped_incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=4.0)
    assert dropped.status == NotificationStatus.SUPPRESSED_NOT_PERSISTENT

    later = dispatcher.evaluate_and_dispatch(dropped_incident, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=100.0)
    assert later.status == NotificationStatus.SUPPRESSED_NOT_PERSISTENT

    dispatcher.shutdown(wait=True)
    assert logger.entries == []  # nothing was ever actually sent or logged
    assert provider.sent_payloads == []


def test_engine_seconds_until_persistent():
    engine = NotificationEngine(FakeProvider())
    assert engine.seconds_until_persistent(10, now=0.0) is None  # not yet critical

    engine.evaluate(priority=90, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)
    assert engine.seconds_until_persistent(10, now=3.0) == pytest.approx(7.0)
    assert engine.seconds_until_persistent(10, now=15.0) == 0.0  # already past persistence window


def test_engine_mark_notified_starts_cooldown_independent_of_notify():
    engine = NotificationEngine(FakeProvider())
    engine.evaluate(priority=90, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=0.0)
    engine.evaluate(priority=90, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=11.0)

    engine.mark_notified(now=11.0)

    status = engine.evaluate(priority=90, critical_threshold=80, persistence_seconds=10, cooldown_seconds=120, now=20.0)
    assert status == NotificationStatus.SUPPRESSED_COOLDOWN

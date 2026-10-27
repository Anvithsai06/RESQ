"""
Notification engine — WORKFLOW.md Phase 12.

Notifies the nearest configured government/emergency service when an
Incident State crosses a persistent critical condition. This is alerting,
not autonomous dispatch: RESQ tells a real human at a real service that
attention may be needed; it never commands a response or claims one has
been dispatched.

Design rules (do not violate — see CLAUDE.md):
- Config-driven recipients only (building/emergency_contacts.json).
- Threshold + persistence gated, with a cooldown to avoid duplicate alerts.
- Payload mirrors the Incident State's explainability (contributors,
  confidence, uncertainty) — never assert more certainty than the
  detections support.
- Fire-and-forget: sending must never block the main pipeline.
- Every attempt (sent / failed / suppressed) is logged.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol


class NotificationStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED_COOLDOWN = "suppressed_cooldown"
    SUPPRESSED_NOT_PERSISTENT = "suppressed_not_persistent"
    PENDING = "pending"
    NO_RECIPIENT_CONFIGURED = "no_recipient_configured"


@dataclass
class NotificationPayload:
    building_id: str
    camera_id: str
    priority: float
    top_contributors: list[str]
    affected_zones: list[str]
    exit_states: dict[str, str]
    confidence: float
    uncertainty: bool
    recipient_service_id: str
    recipient_name: str
    channel_type: str
    channel_target: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class NotificationResult:
    status: NotificationStatus
    detail: str = ""


class NotificationProvider(Protocol):
    """Adapter interface. Implement one of these per real channel
    (Twilio SMS, SMTP email, generic webhook) — all behind this interface
    so the trigger/cooldown logic below never changes."""

    def send(self, payload: NotificationPayload) -> NotificationResult:
        ...


class MockProvider:
    """Default provider for the demo. Logs and returns SENT. Swap for a
    real adapter (Twilio/SMTP/webhook) only if time permits — the demo
    must work end-to-end on this provider alone."""

    def send(self, payload: NotificationPayload) -> NotificationResult:
        print(
            f"[MOCK NOTIFY] {payload.recipient_name} "
            f"({payload.channel_type} -> {payload.channel_target}) | "
            f"priority={payload.priority} zones={payload.affected_zones} "
            f"confidence={payload.confidence} uncertainty={payload.uncertainty}"
        )
        return NotificationResult(status=NotificationStatus.SENT, detail="mock provider")


class NotificationEngine:
    """
    Gates and dispatches notifications based on Incident State.

    Usage (per incident tick):
        engine.evaluate(incident_state, contacts_config, thresholds_config)
    """

    def __init__(self, provider: NotificationProvider | None = None):
        self.provider = provider or MockProvider()
        self._critical_since: float | None = None
        self._last_notified_at: float | None = None

    def evaluate(
        self,
        priority: float,
        critical_threshold: float,
        persistence_seconds: float,
        cooldown_seconds: float,
        now: float | None = None,
    ) -> NotificationStatus:
        """
        Returns the status for this tick without necessarily sending.
        Call `notify(...)` separately once this returns a state that
        warrants dispatch, so the caller controls payload construction.
        """
        now = now if now is not None else time.time()

        if priority < critical_threshold:
            self._critical_since = None
            return NotificationStatus.SUPPRESSED_NOT_PERSISTENT

        if self._critical_since is None:
            self._critical_since = now

        held_for = now - self._critical_since
        if held_for < persistence_seconds:
            return NotificationStatus.PENDING

        if self._last_notified_at is not None and (now - self._last_notified_at) < cooldown_seconds:
            return NotificationStatus.SUPPRESSED_COOLDOWN

        return NotificationStatus.SENT  # caller should now build a payload and call notify()

    def notify(self, payload: NotificationPayload, now: float | None = None) -> NotificationResult:
        result = self.provider.send(payload)
        if result.status == NotificationStatus.SENT:
            self._last_notified_at = now if now is not None else time.time()
        return result

    def mark_notified(self, now: float | None = None) -> None:
        """Starts the cooldown window immediately, independent of whether
        an async send has completed yet. NotificationDispatcher calls this
        the moment it *decides* to notify (possibly several recipients,
        each sent on a background thread) rather than waiting for each
        send to resolve — the cooldown must start at decision time, not at
        each individual delivery's completion time."""
        self._last_notified_at = now if now is not None else time.time()

    def seconds_until_persistent(self, persistence_seconds: float, now: float | None = None) -> float | None:
        """Seconds remaining before a currently-critical condition would
        satisfy the persistence requirement, or None if the condition
        isn't currently critical. Powers dashboard messaging like
        "condition must persist Ns more" (WORKFLOW.md's demo script)."""
        if self._critical_since is None:
            return None
        now = now if now is not None else time.time()
        return max(0.0, persistence_seconds - (now - self._critical_since))

    def is_alert_latched(self, latch_seconds: float, now: float | None = None) -> bool:
        """True while a real notification fired within the last
        `latch_seconds` (by convention, notification_persistence_seconds —
        the caller reuses that same config value, no separate knob).

        Purely a *display* read: it does not affect evaluate()'s
        threshold/persistence/cooldown gating at all. It exists so the
        dashboard can keep an incident visibly flagged as an active alert
        for a stable window after it fires, instead of flickering the
        instant priority next dips below the critical threshold on a noisy
        frame — the underlying priority number and band stay honest and
        unlatched; only this separate flag latches."""
        if self._last_notified_at is None:
            return False
        now = now if now is not None else time.time()
        return (now - self._last_notified_at) < latch_seconds


@dataclass
class EmergencyContact:
    service_id: str
    service_type: str
    name: str
    channels: list[dict]  # [{"type": "webhook"|"sms"|"email", "target": "..."}, ...]
    notify_for_zone_types: list[str]
    priority_rank: int
    distance_note: str = ""


class EmergencyContactsDirectory:
    """Loads building/emergency_contacts.json — RESQ never infers or
    guesses a recipient; it only ever notifies services configured here."""

    def __init__(self, contacts: list[EmergencyContact]):
        self.contacts = sorted(contacts, key=lambda c: c.priority_rank)

    @classmethod
    def from_file(cls, path: str | Path) -> "EmergencyContactsDirectory":
        with open(path) as f:
            config = json.load(f)
        contacts = [
            EmergencyContact(
                service_id=c["service_id"],
                service_type=c["service_type"],
                name=c["name"],
                channels=c["channels"],
                notify_for_zone_types=c.get("notify_for_zone_types", []),
                priority_rank=c.get("priority_rank", 999),
                distance_note=c.get("distance_note", ""),
            )
            for c in config["contacts"]
        ]
        return cls(contacts)

    def select_for_zone_types(self, zone_types: set[str]) -> list[EmergencyContact]:
        """Every configured contact whose notify_for_zone_types intersects
        the given set, ordered by priority_rank. Not "just the single
        nearest" — a danger-zone incident is expected to reach fire,
        police, *and* EMS if all three are configured for "danger"."""
        matches = [c for c in self.contacts if set(c.notify_for_zone_types) & zone_types]
        return sorted(matches, key=lambda c: c.priority_rank)


def build_payloads(incident_state, recipients: list[EmergencyContact], building_id: str) -> list[NotificationPayload]:
    """One payload per recipient, each mirroring the Incident State's own
    explainability. A contact's first configured channel is used — fanning
    a single alert out across all of a contact's channels is a possible
    future enhancement, not needed for the demo."""
    payloads = []
    for contact in recipients:
        channel = contact.channels[0]
        payloads.append(
            NotificationPayload(
                building_id=building_id,
                camera_id=incident_state.camera_id,
                priority=incident_state.priority,
                top_contributors=incident_state.contributors,
                affected_zones=incident_state.affected_zones,
                exit_states={e.exit_id: e.state for e in incident_state.exits},
                confidence=incident_state.confidence,
                uncertainty=incident_state.uncertainty,
                recipient_service_id=contact.service_id,
                recipient_name=contact.name,
                channel_type=channel["type"],
                channel_target=channel["target"],
                timestamp=incident_state.timestamp,
            )
        )
    return payloads


class NotificationLogger(Protocol):
    """Every attempt (sent/failed/suppressed) must be logged — see
    CLAUDE.md — so the dashboard can show an honest status, never a
    fabricated one."""

    def log(self, payload: NotificationPayload, result: NotificationResult) -> None:
        ...


class InMemoryNotificationLogger:
    """Default logger — no Supabase project configured yet. Thread-safe
    since NotificationDispatcher logs from background threads."""

    def __init__(self):
        self.entries: list[tuple[NotificationPayload, NotificationResult]] = []
        self._lock = threading.Lock()

    def log(self, payload: NotificationPayload, result: NotificationResult) -> None:
        with self._lock:
            self.entries.append((payload, result))


class SupabaseNotificationLogger:
    """Writes each attempt to Supabase's `notifications` table (see
    supabase/migrations/0001_init.sql). Takes an already-constructed
    supabase-py Client — wiring the client itself (SUPABASE_URL /
    SUPABASE_SERVICE_ROLE_KEY from backend/config/settings.py) is a
    Phase 14 integration concern, not this module's."""

    def __init__(self, client, building_id: str, incident_id: int | None = None):
        self._client = client
        self.building_id = building_id
        self.incident_id = incident_id

    def log(self, payload: NotificationPayload, result: NotificationResult) -> None:
        self._client.table("notifications").insert(
            {
                "incident_id": self.incident_id,
                "building_id": self.building_id,
                "recipient_service_id": payload.recipient_service_id,
                "recipient_name": payload.recipient_name,
                "channel_type": payload.channel_type,
                "status": result.status.value,
                "payload": asdict(payload),
                "detail": result.detail,
            }
        ).execute()


@dataclass
class DispatchOutcome:
    """What NotificationDispatcher.evaluate_and_dispatch returns for this
    tick — dispatch is fire-and-forget, so this reflects the *decision*
    made right now, not confirmed delivery of any recipient's send."""

    status: NotificationStatus
    reason: str | None
    recipients: list[EmergencyContact] = field(default_factory=list)
    dispatched_at: float | None = None


class NotificationDispatcher:
    """Ties NotificationEngine's threshold/persistence/cooldown state
    machine to real recipient selection, payload construction, and
    fire-and-forget sending — the piece WORKFLOW.md Phase 12 calls "wire
    it into the pipeline"."""

    def __init__(
        self,
        engine: NotificationEngine,
        contacts: EmergencyContactsDirectory,
        zone_types: dict[str, str],
        building_id: str,
        logger: NotificationLogger | None = None,
        max_workers: int = 2,
    ):
        self.engine = engine
        self.contacts = contacts
        self.zone_types = zone_types
        self.building_id = building_id
        self.logger = logger or InMemoryNotificationLogger()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._last_notified_contributors: frozenset[str] = frozenset()

    def _affected_zone_types(self, incident_state) -> set[str]:
        return {self.zone_types[zid] for zid in incident_state.affected_zones if zid in self.zone_types}

    def evaluate_and_dispatch(
        self,
        incident_state,
        critical_threshold: float,
        persistence_seconds: float,
        cooldown_seconds: float,
        now: float | None = None,
    ) -> DispatchOutcome:
        """Never blocks: any actual sending happens on a background
        thread. Returns immediately with this tick's decision."""
        now = now if now is not None else time.time()

        status = self.engine.evaluate(incident_state.priority, critical_threshold, persistence_seconds, cooldown_seconds, now)

        current_contributors = frozenset(incident_state.contributors)
        if status == NotificationStatus.SUPPRESSED_COOLDOWN and (current_contributors - self._last_notified_contributors):
            # WORKFLOW.md: re-fire during cooldown if a materially new
            # hazard/zone contributor has appeared, even though the raw
            # persistence/threshold state machine alone would suppress it.
            status = NotificationStatus.SENT

        if status == NotificationStatus.SUPPRESSED_NOT_PERSISTENT:
            return DispatchOutcome(status=status, reason=f"priority {incident_state.priority:.0f} below critical threshold {critical_threshold:.0f}")

        if status == NotificationStatus.PENDING:
            remaining = self.engine.seconds_until_persistent(persistence_seconds, now)
            reason = f"condition must persist {remaining:.0f}s more" if remaining is not None else "condition persisting"
            return DispatchOutcome(status=status, reason=reason)

        if status == NotificationStatus.SUPPRESSED_COOLDOWN:
            return DispatchOutcome(status=status, reason=f"already notified within the last {cooldown_seconds:.0f}s cooldown window")

        # status == SENT: threshold + persistence satisfied (and either out
        # of cooldown, or a new contributor overrode it) — find recipients.
        affected_types = self._affected_zone_types(incident_state)
        recipients = self.contacts.select_for_zone_types(affected_types)
        if not recipients:
            return DispatchOutcome(
                status=NotificationStatus.NO_RECIPIENT_CONFIGURED,
                reason=f"no configured emergency contact for affected zone types: {sorted(affected_types)}",
            )

        self._last_notified_contributors = current_contributors
        self.engine.mark_notified(now)

        for payload in build_payloads(incident_state, recipients, self.building_id):
            self._executor.submit(self._send_and_log, payload)

        return DispatchOutcome(status=NotificationStatus.SENT, reason=None, recipients=recipients, dispatched_at=now)

    def _send_and_log(self, payload: NotificationPayload) -> None:
        try:
            result = self.engine.provider.send(payload)
        except Exception as exc:  # a real provider (webhook/SMS/email) can raise on network failure
            result = NotificationResult(status=NotificationStatus.FAILED, detail=str(exc))
        self.logger.log(payload, result)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

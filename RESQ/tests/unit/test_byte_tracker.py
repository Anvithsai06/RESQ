"""
Unit tests for ByteTrack tracking (WORKFLOW.md Phase 4).

Covers the properties WORKFLOW.md's Phase 15 hardening checklist cares
about: stable IDs across consecutive frames, IDs not resetting
unnecessarily (including through the low-confidence second-stage match and
brief occlusion), and new tracks only spawning above new_track_thresh.
"""
from vision.detection.detector import Detection
from vision.tracking.byte_tracker import ByteTrackConfig, ByteTracker


def make_detection(bbox, confidence, class_name="person", timestamp=0.0):
    return Detection(
        class_name=class_name,
        confidence=confidence,
        bbox=bbox,
        timestamp=timestamp,
        camera_id="CAM-01",
        validated=True,
    )


def test_stable_id_across_consecutive_frames():
    tracker = ByteTracker(camera_id="CAM-01")

    boxes_over_time = [
        (100, 100, 150, 200),
        (105, 100, 155, 200),
        (110, 101, 160, 201),
        (116, 101, 166, 201),
    ]

    track_ids = []
    for i, box in enumerate(boxes_over_time):
        tracks = tracker.update([make_detection(box, 0.9, timestamp=float(i))], timestamp=float(i))
        assert len(tracks) == 1
        track_ids.append(tracks[0].track_id)

    assert len(set(track_ids)) == 1  # same ID throughout


def test_two_people_get_distinct_stable_ids():
    tracker = ByteTracker(camera_id="CAM-01")

    for i in range(3):
        dets = [
            make_detection((100 + i, 100, 150 + i, 200), 0.9, timestamp=float(i)),
            make_detection((500 + i, 100, 550 + i, 200), 0.9, timestamp=float(i)),
        ]
        tracks = tracker.update(dets, timestamp=float(i))
        assert len(tracks) == 2

    ids = {t.track_id for t in tracks}
    assert len(ids) == 2


def test_new_track_requires_new_track_thresh():
    config = ByteTrackConfig(track_high_thresh=0.5, new_track_thresh=0.6)
    tracker = ByteTracker(config=config, camera_id="CAM-01")

    # confidence 0.55 clears track_high_thresh (0.5) but not new_track_thresh (0.6)
    tracks = tracker.update([make_detection((0, 0, 50, 50), 0.55)], timestamp=0.0)

    assert tracks == []


def test_low_confidence_second_stage_preserves_track_id():
    config = ByteTrackConfig(track_high_thresh=0.5, track_low_thresh=0.1, new_track_thresh=0.6)
    tracker = ByteTracker(config=config, camera_id="CAM-01")

    initial = tracker.update([make_detection((100, 100, 150, 200), 0.9, timestamp=0.0)], timestamp=0.0)
    assert len(initial) == 1
    original_id = initial[0].track_id

    # Same person, but this frame's detection is low-confidence (e.g. brief
    # motion blur) — ByteTrack should still match it via the second stage
    # rather than dropping the detection or spawning a new track.
    second = tracker.update([make_detection((101, 100, 151, 200), 0.2, timestamp=1.0)], timestamp=1.0)

    assert len(second) == 1
    assert second[0].track_id == original_id


def test_track_survives_brief_occlusion_then_reidentifies():
    config = ByteTrackConfig(track_buffer=5)
    tracker = ByteTracker(config=config, camera_id="CAM-01")

    first = tracker.update([make_detection((100, 100, 150, 200), 0.9, timestamp=0.0)], timestamp=0.0)
    original_id = first[0].track_id

    # Occluded for a couple of frames — no detections at all.
    empty1 = tracker.update([], timestamp=1.0)
    empty2 = tracker.update([], timestamp=2.0)
    assert empty1 == []
    assert empty2 == []

    # Reappears within the track_buffer window at roughly the same place.
    reappeared = tracker.update([make_detection((102, 101, 152, 201), 0.9, timestamp=3.0)], timestamp=3.0)

    assert len(reappeared) == 1
    assert reappeared[0].track_id == original_id


def test_track_removed_after_exceeding_buffer_gets_new_id():
    config = ByteTrackConfig(track_buffer=1)
    tracker = ByteTracker(config=config, camera_id="CAM-01")

    first = tracker.update([make_detection((100, 100, 150, 200), 0.9, timestamp=0.0)], timestamp=0.0)
    original_id = first[0].track_id

    # Unmatched for longer than track_buffer=1 frame.
    tracker.update([], timestamp=1.0)
    tracker.update([], timestamp=2.0)
    tracker.update([], timestamp=3.0)

    reappeared = tracker.update([make_detection((100, 100, 150, 200), 0.9, timestamp=4.0)], timestamp=4.0)

    assert len(reappeared) == 1
    assert reappeared[0].track_id != original_id


def test_trajectory_accumulates_positions():
    tracker = ByteTracker(camera_id="CAM-01")

    for i in range(3):
        tracks = tracker.update(
            [make_detection((100 + 10 * i, 100, 150 + 10 * i, 200), 0.9, timestamp=float(i))],
            timestamp=float(i),
        )

    assert len(tracks[0].trajectory) == 3


def test_config_loads_from_real_bytetrack_yaml():
    config = ByteTrackConfig.from_file("configs/bytetrack.yaml")

    assert config.track_high_thresh == 0.5
    assert config.track_low_thresh == 0.1
    assert config.new_track_thresh == 0.6
    assert config.track_buffer == 30
    assert config.match_thresh == 0.8
    assert config.fuse_score is True

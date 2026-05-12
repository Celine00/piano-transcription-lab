from piano_transcription_lab.midi_cleanup import CleanupConfig, NoteEvent, cleanup_notes


def test_cleanup_notes_filters_short_and_quiet_notes_then_quantizes():
    notes = [
        NoteEvent(pitch=60, start=0.011, end=0.041, velocity=80),
        NoteEvent(pitch=64, start=0.113, end=0.401, velocity=5),
        NoteEvent(pitch=67, start=0.113, end=0.401, velocity=80),
    ]

    cleaned = cleanup_notes(
        notes,
        CleanupConfig(min_duration_seconds=0.05, min_velocity=10, quantize_seconds=0.125),
    )

    assert cleaned == [
        NoteEvent(pitch=67, start=0.125, end=0.375, velocity=80),
    ]


def test_cleanup_notes_merges_same_pitch_notes_with_small_gap():
    notes = [
        NoteEvent(pitch=60, start=0.0, end=0.2, velocity=64),
        NoteEvent(pitch=60, start=0.21, end=0.4, velocity=70),
    ]

    cleaned = cleanup_notes(notes, CleanupConfig(merge_gap_seconds=0.025))

    assert cleaned == [
        NoteEvent(pitch=60, start=0.0, end=0.4, velocity=70),
    ]


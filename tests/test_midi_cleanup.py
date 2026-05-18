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


def test_clean_midi_file_applies_filters_quantization_merging_and_tail_clamp(tmp_path):
    mido = __import__("mido")
    from piano_transcription_lab.midi_cleanup import clean_midi_file

    source = tmp_path / "raw.mid"
    target = tmp_path / "clean.mid"

    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    track.append(mido.Message("note_on", note=60, velocity=80, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=24))  # 25ms, too short
    track.append(mido.Message("note_on", note=62, velocity=5, time=216))
    track.append(mido.Message("note_off", note=62, velocity=0, time=240))  # quiet
    track.append(mido.Message("note_on", note=64, velocity=80, time=0))
    track.append(mido.Message("note_off", note=64, velocity=0, time=240))
    track.append(mido.Message("note_on", note=64, velocity=70, time=12))  # 12.5ms gap
    track.append(mido.Message("note_off", note=64, velocity=0, time=228))
    track.append(mido.Message("note_on", note=67, velocity=90, time=2400))  # past clamp
    track.append(mido.Message("note_off", note=67, velocity=0, time=480))
    mid.save(source)

    clean_midi_file(
        source,
        target,
        CleanupConfig(
            min_duration_seconds=0.05,
            min_velocity=10,
            quantize_seconds=0.125,
            merge_gap_seconds=0.025,
            max_end_seconds=1.1,
        ),
    )

    cleaned = mido.MidiFile(target)
    notes = []
    starts = {}
    elapsed = 0.0
    tempo = mido.bpm2tempo(120)
    for msg in mido.merge_tracks(cleaned.tracks):
        elapsed += mido.tick2second(msg.time, cleaned.ticks_per_beat, tempo)
        if msg.type == "set_tempo":
            tempo = msg.tempo
        if msg.type == "note_on" and msg.velocity > 0:
            starts[msg.note] = (elapsed, msg.velocity)
        elif msg.type in {"note_off", "note_on"} and msg.note in starts:
            start, velocity = starts.pop(msg.note)
            notes.append((msg.note, round(start, 3), round(elapsed, 3), velocity))

    assert notes == [(64, 0.5, 1.0, 80)]


def test_cleanup_notes_melody_mode_keeps_top_note_per_quantized_onset():
    notes = [
        NoteEvent(pitch=55, start=0.01, end=0.4, velocity=90),
        NoteEvent(pitch=72, start=0.02, end=0.3, velocity=70),
        NoteEvent(pitch=67, start=0.13, end=0.5, velocity=80),
        NoteEvent(pitch=76, start=0.14, end=0.6, velocity=60),
    ]

    cleaned = cleanup_notes(
        notes,
        CleanupConfig(quantize_seconds=0.125, reduction_mode="melody"),
    )

    assert cleaned == [
        NoteEvent(pitch=72, start=0.0, end=0.125, velocity=70),
        NoteEvent(pitch=76, start=0.125, end=0.625, velocity=60),
    ]


def test_cleanup_notes_piano_reduction_limits_notes_per_onset_by_velocity():
    notes = [
        NoteEvent(pitch=48, start=0.01, end=0.4, velocity=40),
        NoteEvent(pitch=52, start=0.02, end=0.4, velocity=90),
        NoteEvent(pitch=55, start=0.03, end=0.4, velocity=70),
        NoteEvent(pitch=59, start=0.04, end=0.4, velocity=60),
    ]

    cleaned = cleanup_notes(
        notes,
        CleanupConfig(
            quantize_seconds=0.125,
            reduction_mode="piano-reduction",
            max_notes_per_onset=2,
        ),
    )

    assert cleaned == [
        NoteEvent(pitch=52, start=0.0, end=0.375, velocity=90),
        NoteEvent(pitch=55, start=0.0, end=0.375, velocity=70),
    ]

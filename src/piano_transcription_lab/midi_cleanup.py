from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import shutil


@dataclass(frozen=True)
class NoteEvent:
    pitch: int
    start: float
    end: float
    velocity: int


@dataclass(frozen=True)
class CleanupConfig:
    min_duration_seconds: float = 0.0
    min_velocity: int = 0
    quantize_seconds: float | None = None
    merge_gap_seconds: float = 0.0
    min_pitch: int = 21
    max_pitch: int = 108
    max_end_seconds: float | None = None
    reduction_mode: str = "full"
    max_notes_per_onset: int = 4
    auto_key: bool = False
    notation_mode: str = "full"
    hand_split_pitch: int = 60
    measure_seconds: float = 2.0
    simple_duration_seconds: float = 0.25
    max_right_notes_per_measure: int = 8
    max_left_notes_per_measure: int = 8
    extra: dict = field(default_factory=dict)


def cleanup_notes(notes: list[NoteEvent], config: CleanupConfig) -> list[NoteEvent]:
    trimmed = [
        NoteEvent(
            pitch=note.pitch,
            start=note.start,
            end=min(note.end, config.max_end_seconds)
            if config.max_end_seconds is not None
            else note.end,
            velocity=note.velocity,
        )
        for note in notes
        if config.max_end_seconds is None or note.start < config.max_end_seconds
    ]

    filtered = [
        note
        for note in trimmed
        if note.end > note.start
        and note.end - note.start >= config.min_duration_seconds
        and note.velocity >= config.min_velocity
        and config.min_pitch <= note.pitch <= config.max_pitch
    ]

    quantized = [_quantize_note(note, config.quantize_seconds) for note in filtered]
    quantized = [note for note in quantized if note.end > note.start]
    keyed = _transpose_to_simple_key(quantized, config) if config.auto_key else quantized
    arranged = _arrange_beginner_notation(keyed, config) if config.notation_mode == "beginner" else keyed
    reduced = _reduce_note_density(arranged, config)

    return _merge_close_repeats(sorted(reduced, key=lambda note: (note.start, note.pitch)), config)


def _arrange_beginner_notation(notes: list[NoteEvent], config: CleanupConfig) -> list[NoteEvent]:
    if not notes:
        return notes

    by_measure: dict[int, list[NoteEvent]] = defaultdict(list)
    for note in notes:
        by_measure[int(note.start // config.measure_seconds)].append(note)

    arranged: list[NoteEvent] = []
    for measure_index in sorted(by_measure):
        measure_start = measure_index * config.measure_seconds
        measure_notes = by_measure[measure_index]
        right_notes = [note for note in measure_notes if note.pitch >= config.hand_split_pitch]
        left_notes = [note for note in measure_notes if note.pitch < config.hand_split_pitch]
        arranged.extend(_select_beginner_melody(right_notes, measure_start, config))
        arranged.extend(_build_beginner_left_hand(left_notes, measure_start, config))

    return sorted(arranged, key=lambda note: (note.start, note.pitch))


def _select_beginner_melody(
    notes: list[NoteEvent],
    measure_start: float,
    config: CleanupConfig,
) -> list[NoteEvent]:
    if not notes:
        return []

    by_slot: dict[int, list[NoteEvent]] = defaultdict(list)
    for note in notes:
        slot = int(round((note.start - measure_start) / config.simple_duration_seconds))
        by_slot[slot].append(note)

    selected: list[NoteEvent] = []
    for slot in sorted(by_slot)[: config.max_right_notes_per_measure]:
        start = round(measure_start + slot * config.simple_duration_seconds, 6)
        note = max(
            by_slot[slot],
            key=lambda item: (
                -abs(item.start - start),
                item.pitch,
                item.velocity,
                item.end - item.start,
            ),
        )
        selected.append(
            NoteEvent(
                pitch=note.pitch,
                start=start,
                end=round(start + config.simple_duration_seconds, 6),
                velocity=note.velocity,
            )
        )
    return selected


def _build_beginner_left_hand(
    notes: list[NoteEvent],
    measure_start: float,
    config: CleanupConfig,
) -> list[NoteEvent]:
    if not notes:
        return []

    bass = min(notes, key=lambda note: (note.pitch, -note.velocity))
    count = max(1, config.max_left_notes_per_measure)
    return [
        NoteEvent(
            pitch=bass.pitch,
            start=round(measure_start + index * config.simple_duration_seconds, 6),
            end=round(measure_start + (index + 1) * config.simple_duration_seconds, 6),
            velocity=bass.velocity,
        )
        for index in range(count)
    ]


def clean_midi_file(source: Path, target: Path, config: CleanupConfig) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        import mido
    except ImportError:
        shutil.copyfile(source, target)
        return

    midi = mido.MidiFile(source)
    notes, tempo = _extract_note_events(midi, mido)
    cleaned = cleanup_notes(notes, config)
    _write_note_events(cleaned, target, midi.ticks_per_beat, tempo, mido)


def _extract_note_events(midi, mido) -> tuple[list[NoteEvent], int]:
    tempo = mido.bpm2tempo(120)
    output_tempo = tempo
    elapsed_seconds = 0.0
    active_notes = defaultdict(list)
    notes: list[NoteEvent] = []

    for msg in mido.merge_tracks(midi.tracks):
        elapsed_seconds += mido.tick2second(msg.time, midi.ticks_per_beat, tempo)
        if msg.type == "set_tempo":
            tempo = msg.tempo
            output_tempo = msg.tempo
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            active_notes[(getattr(msg, "channel", 0), msg.note)].append(
                (elapsed_seconds, msg.velocity)
            )
            continue
        if msg.type in {"note_off", "note_on"}:
            key = (getattr(msg, "channel", 0), msg.note)
            if active_notes[key]:
                start, velocity = active_notes[key].pop(0)
                notes.append(
                    NoteEvent(
                        pitch=msg.note,
                        start=start,
                        end=elapsed_seconds,
                        velocity=velocity,
                    )
                )

    return notes, output_tempo


def _write_note_events(
    notes: list[NoteEvent],
    target: Path,
    ticks_per_beat: int,
    tempo: int,
    mido,
) -> None:
    midi = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))

    events = []
    for note in notes:
        start_tick = int(round(mido.second2tick(note.start, ticks_per_beat, tempo)))
        end_tick = int(round(mido.second2tick(note.end, ticks_per_beat, tempo)))
        if end_tick <= start_tick:
            continue
        events.append(
            (
                start_tick,
                1,
                mido.Message("note_on", note=note.pitch, velocity=note.velocity, time=0),
            )
        )
        events.append(
            (
                end_tick,
                0,
                mido.Message("note_off", note=note.pitch, velocity=0, time=0),
            )
        )

    previous_tick = 0
    for tick, _priority, msg in sorted(
        events,
        key=lambda event: (event[0], event[1], event[2].note),
    ):
        msg.time = max(0, tick - previous_tick)
        previous_tick = tick
        track.append(msg)
    track.append(mido.MetaMessage("end_of_track", time=0))
    midi.save(target)


def _quantize_note(note: NoteEvent, step: float | None) -> NoteEvent:
    if not step:
        return note
    start = _quantize_value(note.start, step)
    end = _quantize_value(note.end, step)
    return NoteEvent(pitch=note.pitch, start=start, end=end, velocity=note.velocity)


def _quantize_value(value: float, step: float) -> float:
    return round(round(value / step) * step, 6)


def _reduce_note_density(notes: list[NoteEvent], config: CleanupConfig) -> list[NoteEvent]:
    if config.reduction_mode == "full":
        return notes

    by_start: dict[float, list[NoteEvent]] = defaultdict(list)
    for note in notes:
        by_start[note.start].append(note)

    reduced: list[NoteEvent] = []
    for onset_notes in by_start.values():
        if config.reduction_mode == "melody":
            reduced.append(max(onset_notes, key=lambda note: (note.pitch, note.velocity)))
            continue
        if config.reduction_mode == "piano-reduction":
            kept = sorted(
                onset_notes,
                key=lambda note: (note.velocity, note.duration if hasattr(note, "duration") else note.end - note.start),
                reverse=True,
            )[: config.max_notes_per_onset]
            reduced.extend(kept)
            continue
        raise ValueError(f"Unknown reduction mode: {config.reduction_mode}")
    if config.reduction_mode == "melody":
        return _make_monophonic(reduced)
    return reduced


MAJOR_SCALE_INTERVALS = {0, 2, 4, 5, 7, 9, 11}
SIMPLE_MAJOR_KEYS = {
    0: 0,   # C
    7: 1,   # G
    2: 2,   # D
    5: 1,   # F
    9: 3,   # A
    10: 2,  # Bb
}


def _transpose_to_simple_key(notes: list[NoteEvent], config: CleanupConfig) -> list[NoteEvent]:
    if not notes:
        return notes

    source_key = _estimate_major_key(notes)
    shift = _choose_simple_key_shift(source_key, notes, config)
    if shift == 0:
        return notes

    return [
        NoteEvent(
            pitch=note.pitch + shift,
            start=note.start,
            end=note.end,
            velocity=note.velocity,
        )
        for note in notes
    ]


def _estimate_major_key(notes: list[NoteEvent]) -> int:
    pitch_class_weights: dict[int, float] = defaultdict(float)
    for note in notes:
        pitch_class_weights[note.pitch % 12] += max(0.001, note.end - note.start)

    return max(
        range(12),
        key=lambda key: (
            sum(
                weight
                for pitch_class, weight in pitch_class_weights.items()
                if (pitch_class - key) % 12 in MAJOR_SCALE_INTERVALS
            ),
            pitch_class_weights.get(key, 0.0),
            -key,
        ),
    )


def _choose_simple_key_shift(
    source_key: int,
    notes: list[NoteEvent],
    config: CleanupConfig,
) -> int:
    candidates = []
    for target_key, accidental_count in SIMPLE_MAJOR_KEYS.items():
        shift = _nearest_shift(source_key, target_key)
        shifted_pitches = [note.pitch + shift for note in notes]
        if min(shifted_pitches) < config.min_pitch or max(shifted_pitches) > config.max_pitch:
            continue
        candidates.append((accidental_count, abs(shift), shift))

    if not candidates:
        return 0
    return min(candidates)[2]


def _nearest_shift(source_key: int, target_key: int) -> int:
    upward = (target_key - source_key) % 12
    return upward - 12 if upward > 6 else upward


def _make_monophonic(notes: list[NoteEvent]) -> list[NoteEvent]:
    sorted_notes = sorted(notes, key=lambda note: (note.start, note.pitch))
    monophonic: list[NoteEvent] = []
    for index, note in enumerate(sorted_notes):
        next_start = (
            sorted_notes[index + 1].start
            if index + 1 < len(sorted_notes)
            else note.end
        )
        end = min(note.end, next_start)
        if end > note.start:
            monophonic.append(
                NoteEvent(
                    pitch=note.pitch,
                    start=note.start,
                    end=end,
                    velocity=note.velocity,
                )
            )
    return monophonic


def _merge_close_repeats(notes: list[NoteEvent], config: CleanupConfig) -> list[NoteEvent]:
    merged: list[NoteEvent] = []
    for note in notes:
        if merged:
            previous = merged[-1]
            gap = note.start - previous.end
            if note.pitch == previous.pitch and 0 <= gap <= config.merge_gap_seconds:
                merged[-1] = NoteEvent(
                    pitch=previous.pitch,
                    start=previous.start,
                    end=max(previous.end, note.end),
                    velocity=max(previous.velocity, note.velocity),
                )
                continue
        merged.append(note)
    return merged

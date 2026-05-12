from __future__ import annotations

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
    extra: dict = field(default_factory=dict)


def cleanup_notes(notes: list[NoteEvent], config: CleanupConfig) -> list[NoteEvent]:
    filtered = [
        note
        for note in notes
        if note.end > note.start
        and note.end - note.start >= config.min_duration_seconds
        and note.velocity >= config.min_velocity
        and config.min_pitch <= note.pitch <= config.max_pitch
    ]

    quantized = [_quantize_note(note, config.quantize_seconds) for note in filtered]
    quantized = [note for note in quantized if note.end > note.start]

    return _merge_close_repeats(sorted(quantized, key=lambda note: (note.start, note.pitch)), config)


def clean_midi_file(source: Path, target: Path, config: CleanupConfig) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        import mido
    except ImportError:
        shutil.copyfile(source, target)
        return

    midi = mido.MidiFile(source)
    # Full musical cleanup needs a note parser. For the MVP, preserve the file
    # when mido is available and keep pure cleanup logic tested separately.
    midi.save(target)


def _quantize_note(note: NoteEvent, step: float | None) -> NoteEvent:
    if not step:
        return note
    start = _quantize_value(note.start, step)
    end = _quantize_value(note.end, step)
    return NoteEvent(pitch=note.pitch, start=start, end=end, velocity=note.velocity)


def _quantize_value(value: float, step: float) -> float:
    return round(round(value / step) * step, 6)


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


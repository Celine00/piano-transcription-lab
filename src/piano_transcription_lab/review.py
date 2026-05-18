from __future__ import annotations

from pathlib import Path
import json
import xml.etree.ElementTree as ET


def write_review_report(
    clean_midi: Path,
    target: Path,
    config,
    *,
    audio_duration_seconds: float | None = None,
    render_source: str = "musicxml",
    musicxml_path: Path | None = None,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    report = review_midi(
        clean_midi,
        config,
        audio_duration_seconds=audio_duration_seconds,
        render_source=render_source,
        musicxml_path=musicxml_path,
    )
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def review_midi(
    clean_midi: Path,
    config,
    *,
    audio_duration_seconds: float | None = None,
    render_source: str = "musicxml",
    musicxml_path: Path | None = None,
) -> dict:
    try:
        import mido

        notes, midi_length = _read_notes(clean_midi, mido)
    except Exception as exc:
        return {
            "score": 0,
            "score_kind": "readability_without_reference",
            "accuracy_reference": None,
            "decision": "reject",
            "render_source": render_source,
            "issues": ["midi_parse_failed"],
            "metrics": {"error": f"{type(exc).__name__}: {exc}"},
        }

    score = 100
    issues: list[str] = []
    metrics = _build_metrics(notes, midi_length, audio_duration_seconds)
    if musicxml_path is not None:
        metrics["musicxml"] = _read_musicxml_metrics(musicxml_path)

    if render_source != "musicxml":
        score -= 25
        issues.append("musicxml_render_failed")

    if metrics["tail_overrun_seconds"] > 1.0:
        score -= min(30, int(metrics["tail_overrun_seconds"] * 8))
        issues.append("midi_extends_beyond_audio")

    if metrics["notes_per_second"] > 12:
        score -= 35
        issues.append("note_density_too_high")
    elif metrics["notes_per_second"] > 8:
        score -= 12
        issues.append("note_density_high")

    if metrics["max_simultaneous_onsets"] > 8:
        score -= 15
        issues.append("chord_density_too_high")

    if metrics["short_note_ratio"] > 0.15:
        score -= 15
        issues.append("many_short_notes")

    if metrics["quiet_note_ratio"] > 0.15:
        score -= 10
        issues.append("many_quiet_notes")

    musicxml_metrics = metrics.get("musicxml")
    if musicxml_metrics:
        if musicxml_metrics["max_notes_per_measure"] > 32:
            score -= 30
            issues.append("notation_density_too_high")
        elif musicxml_metrics["max_notes_per_measure"] > 24:
            score -= 18
            issues.append("notation_density_high")

        if musicxml_metrics["complexity_score"] > 35:
            score -= 25
            issues.append("notation_complexity_too_high")
        elif musicxml_metrics["complexity_score"] > 24:
            score -= 12
            issues.append("notation_complexity_high")

    score = max(0, min(100, score))
    decision = "pass" if score >= 75 else "warn" if score >= 50 else "reject"
    return {
        "score": score,
        "score_kind": "readability_without_reference",
        "accuracy_reference": None,
        "decision": decision,
        "render_source": render_source,
        "issues": issues,
        "metrics": metrics,
    }


def _read_musicxml_metrics(musicxml_path: Path) -> dict:
    try:
        root = ET.parse(musicxml_path).getroot()
    except ET.ParseError:
        return {"parse_error": True}

    measures = root.findall(".//measure")
    max_notes = 0
    max_pitched = 0
    max_chords = 0
    max_rests = 0
    max_ties = 0
    max_tuplets = 0
    max_voice_count = 0

    for measure in measures:
        notes = measure.findall("note")
        pitched = [note for note in notes if note.find("pitch") is not None]
        chords = [note for note in notes if note.find("chord") is not None]
        rests = [note for note in notes if note.find("rest") is not None]
        ties = [note for note in notes if note.find("tie") is not None]
        tuplets = [note for note in notes if note.find("time-modification") is not None]
        voices = {
            voice.text
            for voice in (note.find("voice") for note in notes)
            if voice is not None and voice.text
        }

        max_notes = max(max_notes, len(notes))
        max_pitched = max(max_pitched, len(pitched))
        max_chords = max(max_chords, len(chords))
        max_rests = max(max_rests, len(rests))
        max_ties = max(max_ties, len(ties))
        max_tuplets = max(max_tuplets, len(tuplets))
        max_voice_count = max(max_voice_count, len(voices))

    complexity_score = (
        max_chords
        + max_ties
        + max_tuplets * 2
        + max(0, max_voice_count - 1) * 8
        + max_rests // 2
    )
    return {
        "parse_error": False,
        "measure_count": len(measures),
        "max_notes_per_measure": max_notes,
        "max_pitched_notes_per_measure": max_pitched,
        "max_chords_per_measure": max_chords,
        "max_rests_per_measure": max_rests,
        "max_ties_per_measure": max_ties,
        "max_tuplets_per_measure": max_tuplets,
        "max_voice_count": max_voice_count,
        "complexity_score": complexity_score,
    }


def _read_notes(midi_path: Path, mido) -> tuple[list[dict], float]:
    midi = mido.MidiFile(midi_path)
    tempo = mido.bpm2tempo(120)
    elapsed = 0.0
    active = {}
    notes = []

    for msg in mido.merge_tracks(midi.tracks):
        elapsed += mido.tick2second(msg.time, midi.ticks_per_beat, tempo)
        if msg.type == "set_tempo":
            tempo = msg.tempo
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            active[(getattr(msg, "channel", 0), msg.note)] = (elapsed, msg.velocity)
            continue
        if msg.type in {"note_off", "note_on"}:
            key = (getattr(msg, "channel", 0), msg.note)
            if key in active:
                start, velocity = active.pop(key)
                if elapsed > start:
                    notes.append(
                        {
                            "pitch": msg.note,
                            "start": start,
                            "end": elapsed,
                            "duration": elapsed - start,
                            "velocity": velocity,
                        }
                    )

    midi_end = max([elapsed] + [note["end"] for note in notes])
    return notes, midi_end


def _build_metrics(
    notes: list[dict],
    midi_length_seconds: float,
    audio_duration_seconds: float | None,
) -> dict:
    note_count = len(notes)
    duration = max(midi_length_seconds, 0.001)
    short_notes = [note for note in notes if note["duration"] < 0.08]
    quiet_notes = [note for note in notes if note["velocity"] < 30]
    onset_buckets = {}
    for note in notes:
        bucket = round(note["start"] / 0.02)
        onset_buckets[bucket] = onset_buckets.get(bucket, 0) + 1

    tail_overrun = 0.0
    if audio_duration_seconds is not None:
        tail_overrun = max(0.0, midi_length_seconds - audio_duration_seconds)

    return {
        "note_count": note_count,
        "midi_length_seconds": round(midi_length_seconds, 3),
        "audio_duration_seconds": round(audio_duration_seconds, 3)
        if audio_duration_seconds is not None
        else None,
        "tail_overrun_seconds": round(tail_overrun, 3),
        "notes_per_second": round(note_count / duration, 3),
        "short_note_ratio": round(len(short_notes) / note_count, 3) if note_count else 0.0,
        "quiet_note_ratio": round(len(quiet_notes) / note_count, 3) if note_count else 0.0,
        "max_simultaneous_onsets": max(onset_buckets.values(), default=0),
    }

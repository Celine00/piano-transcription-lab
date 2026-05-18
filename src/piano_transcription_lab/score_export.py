from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

DEFAULT_HAND_SPLIT_PITCH = 60
MAX_ADAPTIVE_HAND_SPLIT_PITCH = 72
MIN_LEFT_HAND_RATIO = 0.25
TARGET_LEFT_HAND_RATIO = 0.4


def export_musicxml(source: Path, target: Path, config, run_command=subprocess.run) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    score_source = _write_piano_hand_split_midi(
        source,
        target.with_suffix(".hands.mid"),
        split_pitch=getattr(config, "hand_split_pitch", None),
    )
    try:
        run_command([config.musescore, "-o", str(target), str(score_source)], check=True)
        _normalize_hand_musicxml(target)
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    try:
        from music21 import converter
    except ImportError as exc:
        raise RuntimeError("music21 is required to export MusicXML. Install the runtime extras.") from exc

    score = converter.parse(str(score_source))
    score.write("musicxml", fp=str(target))
    _normalize_hand_musicxml(target)


def copy_midi_as_placeholder(source: Path, target: Path, config) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _write_piano_hand_split_midi(source: Path, target: Path, split_pitch: int | None) -> Path:
    try:
        import mido
    except ImportError:
        return source

    midi = mido.MidiFile(source)
    split_pitch = split_pitch or _choose_hand_split_pitch(_read_note_pitches(midi, mido))
    events = _collect_hand_split_events(midi, mido, split_pitch)

    split = mido.MidiFile(ticks_per_beat=midi.ticks_per_beat)
    right_track = _build_track("Right Hand", events["right"], mido)
    left_track = _build_track("Left Hand", events["left"], mido)
    split.tracks.extend([right_track, left_track])
    split.save(target)
    return target


def _read_note_pitches(midi, mido) -> list[int]:
    return [
        msg.note
        for msg in mido.merge_tracks(midi.tracks)
        if msg.type == "note_on" and msg.velocity > 0
    ]


def _choose_hand_split_pitch(pitches: list[int]) -> int:
    if not pitches:
        return DEFAULT_HAND_SPLIT_PITCH

    base_left_count = sum(1 for pitch in pitches if pitch < DEFAULT_HAND_SPLIT_PITCH)
    base_left_ratio = base_left_count / len(pitches)
    if base_left_count == 0 or base_left_ratio >= MIN_LEFT_HAND_RATIO:
        return DEFAULT_HAND_SPLIT_PITCH

    candidates = range(DEFAULT_HAND_SPLIT_PITCH, MAX_ADAPTIVE_HAND_SPLIT_PITCH + 1)
    return min(
        candidates,
        key=lambda split_pitch: abs(
            sum(1 for pitch in pitches if pitch < split_pitch) / len(pitches)
            - TARGET_LEFT_HAND_RATIO
        ),
    )


def _collect_hand_split_events(
    midi,
    mido,
    split_pitch: int,
) -> dict[str, list[tuple[int, int, object]]]:
    elapsed_ticks = 0
    active_notes = {}
    events = {"right": [], "left": []}

    for msg in mido.merge_tracks(midi.tracks):
        elapsed_ticks += msg.time
        if msg.is_meta:
            if msg.type not in {"end_of_track", "track_name"}:
                for hand_events in events.values():
                    hand_events.append((elapsed_ticks, 0, msg.copy(time=0)))
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            hand = "right" if msg.note >= split_pitch else "left"
            key = (getattr(msg, "channel", 0), msg.note)
            active_notes.setdefault(key, []).append(hand)
            events[hand].append(
                (
                    elapsed_ticks,
                    2,
                    msg.copy(time=0, channel=0 if hand == "right" else 1),
                )
            )
            continue
        if msg.type in {"note_off", "note_on"}:
            key = (getattr(msg, "channel", 0), msg.note)
            hand_stack = active_notes.get(key)
            if not hand_stack:
                continue
            hand = hand_stack.pop(0)
            events[hand].append(
                (
                    elapsed_ticks,
                    1,
                    msg.copy(time=0, channel=0 if hand == "right" else 1),
                )
            )

    return events


def _build_track(name: str, events: list[tuple[int, int, object]], mido):
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    previous_tick = 0
    for tick, _priority, msg in sorted(events, key=lambda event: (event[0], event[1])):
        msg.time = max(0, tick - previous_tick)
        previous_tick = tick
        track.append(msg)
    track.append(mido.MetaMessage("end_of_track", time=0))
    return track


def _normalize_hand_musicxml(target: Path) -> None:
    try:
        tree = ET.parse(target)
    except ET.ParseError:
        return

    root = tree.getroot()
    hand_part_ids: dict[str, str] = {}
    for score_part in root.findall(".//score-part"):
        part_id = score_part.attrib.get("id")
        name = score_part.findtext("part-name") or ""
        hand_name = _normalized_hand_name(name)
        if part_id is None or hand_name is None:
            continue
        hand_part_ids[part_id] = hand_name
        part_name = score_part.find("part-name")
        if part_name is not None:
            part_name.text = hand_name
        abbreviation = score_part.find("part-abbreviation")
        if abbreviation is not None:
            abbreviation.text = "R.H." if hand_name == "Right Hand" else "L.H."

    if not hand_part_ids:
        return

    for part in root.findall("part"):
        if part.attrib.get("id") not in hand_part_ids:
            continue
        for staves in part.findall(".//staves"):
            staves.text = "1"
        for staff in part.findall(".//staff"):
            staff.text = "1"
        _remove_extra_staff_elements(part)

    tree.write(target, encoding="utf-8", xml_declaration=True)


def _remove_extra_staff_elements(part: ET.Element) -> None:
    staff_scoped_tags = {"clef", "staff-details", "staff-layout"}
    for parent in part.iter():
        for child in list(parent):
            if child.tag not in staff_scoped_tags:
                continue
            number = child.attrib.get("number")
            if number is not None and number != "1":
                parent.remove(child)


def _normalized_hand_name(name: str) -> str | None:
    if "Right Hand" in name:
        return "Right Hand"
    if "Left Hand" in name:
        return "Left Hand"
    return None

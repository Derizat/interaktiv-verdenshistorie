#!/usr/bin/env python3
"""Generate read-aloud MP3s for every event and every year with Google Cloud Text-to-Speech.

Usage:
    python3 scripts/tts.py            # generate missing clips, update data/audio.json
    python3 scripts/tts.py --prune    # also delete clips no longer referenced

The API key is read from $GOOGLE_TTS_KEY or ~/.config/google-tts/key.

Each clip is named after a hash of the voice and the source text (see clip_id, mirrored by
clipId in index.html). Editing an event's text gives it a new hash, so the page falls back to
the browser voice for that event until this script is run again.
"""
import base64
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT, "audio")
MANIFEST = os.path.join(ROOT, "data", "audio.json")
DEFAULT_VOICE = "da-DK-Chirp3-HD-Charon"


def manifest_voice():
    try:
        return json.load(open(MANIFEST, encoding="utf-8")).get("voice")
    except (OSError, ValueError):
        return None


# TTS_VOICE switches voice; after that the voice in data/audio.json is kept.
VOICE = os.environ.get("TTS_VOICE") or manifest_voice() or DEFAULT_VOICE
YEARS = range(1914, 2026)  # Y0..Y1 in index.html
API = "https://texttospeech.googleapis.com/v1/text:synthesize"


def fnv1a(s):
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def clip_id(*parts):
    return fnv1a("\n".join([VOICE, *map(str, parts)]))


def sentence(s):
    s = " ".join(s.split())
    return s if s.endswith((".", "!", "?")) else s + "."


def clips():
    events = json.load(open(os.path.join(ROOT, "data", "events.json"), encoding="utf-8"))
    out = {clip_id("year", y): f"{y}." for y in YEARS}
    for e in events:
        out[clip_id(e["title"], e["date"], e["text"])] = " ".join(sentence(x) for x in (e["title"], e["date"], e["text"]))
    return out


def api_key():
    key = os.environ.get("GOOGLE_TTS_KEY")
    if not key:
        try:
            key = open(os.path.expanduser("~/.config/google-tts/key")).read().split()[0]
        except (OSError, IndexError):
            sys.exit("Missing API key: set GOOGLE_TTS_KEY or write it to ~/.config/google-tts/key")
    return key


def synthesize(key, text):
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": VOICE[:5], "name": VOICE},
        "audioConfig": {"audioEncoding": "MP3"},
    }).encode()
    req = urllib.request.Request(API, body, {"Content-Type": "application/json", "X-Goog-Api-Key": key})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return base64.b64decode(json.load(r)["audioContent"])
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise RuntimeError(f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException):
            if attempt == 4:
                raise
        time.sleep(2 ** attempt)


def main():
    prune = "--prune" in sys.argv[1:]
    os.makedirs(AUDIO_DIR, exist_ok=True)
    wanted = clips()
    todo = {cid: text for cid, text in wanted.items() if not os.path.exists(os.path.join(AUDIO_DIR, cid + ".mp3"))}
    print(f"{VOICE}: {len(wanted)} clips, {len(todo)} to generate ({sum(map(len, todo.values()))} characters)")

    key = api_key() if todo else None
    failed = []

    def work(item):
        cid, text = item
        try:
            data = synthesize(key, text)
        except Exception as e:
            failed.append(cid)
            print(f"  FAILED {cid} ({text[:40]}…): {e}")
            return
        tmp = os.path.join(AUDIO_DIR, cid + ".tmp")
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, os.path.join(AUDIO_DIR, cid + ".mp3"))

    with ThreadPoolExecutor(4) as pool:
        for i, _ in enumerate(pool.map(work, todo.items()), 1):
            if i % 50 == 0:
                print(f"  {i}/{len(todo)}")

    present = sorted(cid for cid in wanted if os.path.exists(os.path.join(AUDIO_DIR, cid + ".mp3")))
    old_voice = manifest_voice()
    if failed and old_voice and VOICE != old_voice:
        # Keep the old voice's manifest (and its clips) until the new voice has generated cleanly.
        sys.exit(f"{len(failed)} clips failed; data/audio.json still uses {old_voice}")
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump({"voice": VOICE, "clips": present}, f, separators=(",", ":"))
        f.write("\n")

    stale = sorted(n for n in os.listdir(AUDIO_DIR) if n.endswith(".mp3") and n[:-4] not in wanted)
    if stale and prune and failed:
        print(f"Not deleting {len(stale)} unused clips because some clips failed")
    elif stale and prune:
        for n in stale:
            os.remove(os.path.join(AUDIO_DIR, n))
        print(f"Deleted {len(stale)} unused clips")
    elif stale:
        print(f"{len(stale)} unused clips in audio/ (run with --prune to delete them)")
    print(f"Manifest: {len(present)}/{len(wanted)} clips" + (f", {len(failed)} failed" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

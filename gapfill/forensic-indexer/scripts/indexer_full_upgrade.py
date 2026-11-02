#!/usr/bin/env python3
"""Full upgrade: recompute prosody, keywords, proper nouns, numbers,
   re‑score vagueness, and set layer for ALL utterances.
   Sets feature_version = 2 after success.
"""
import os, sys, sqlite3, json, re, math
from collections import Counter
from pathlib import Path

import torch
import torchaudio
import numpy as np
from scipy.fft import rfft, rfftfreq

PROJECT = os.path.expanduser("~/forensic-indexer")
DB = f"{PROJECT}/data/vault.db"
NEW_VERSION = 2

# Stopwords – expanded
STOPWORDS = {
    'i','you','he','she','it','we','they','me','him','her','us','them',
    'my','your','his','her','our','their','a','an','the','and','or','but',
    'so','for','nor','on','at','to','by','in','of','with','without','about',
    'like','just','so','then','now','yeah','okay','uh','um','hmm','oh',
    'well','really','very','actually','gonna','wanna','got','get','let',
    'see','say','go','come','look','know','think','mean','want','need'
}

def load_segment(file_path, start_ms, end_ms):
    """Load mono audio segment using torchaudio."""
    start = start_ms / 1000.0
    duration = (end_ms - start_ms) / 1000.0
    if duration < 0.1:
        return None, None
    try:
        waveform, sr = torchaudio.load(file_path, frame_offset=int(start * sr),
                                       num_frames=int(duration * sr))
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        audio = waveform.squeeze(0).numpy()
        return audio, sr
    except Exception as e:
        return None, None

def compute_prosody(audio, sr):
    """Return dict of pitch_mean, pitch_std, energy_mean, spectral_centroid, zcr."""
    if audio is None or len(audio) < sr * 0.1:
        return None
    energy = np.sqrt(np.mean(audio**2))
    # Pitch: FFT peak in 50-300 Hz
    fft = np.abs(rfft(audio))
    freqs = rfftfreq(len(audio), 1/sr)
    mask = (freqs >= 50) & (freqs <= 300)
    if np.any(mask):
        pitch_mean = freqs[mask][np.argmax(fft[mask])]
    else:
        pitch_mean = 0.0
    # Pitch std – frame‑based
    frame_len = int(0.025 * sr)
    hop = int(0.010 * sr)
    pitches = []
    for i in range(0, len(audio)-frame_len, hop):
        frame = audio[i:i+frame_len]
        fft_f = np.abs(rfft(frame))
        freqs_f = rfftfreq(len(frame), 1/sr)
        mask_f = (freqs_f >= 50) & (freqs_f <= 300)
        if np.any(mask_f):
            p = freqs_f[mask_f][np.argmax(fft_f[mask_f])]
            pitches.append(p)
    pitch_std = np.std(pitches) if pitches else 0.0
    # Spectral centroid
    magnitudes = np.abs(rfft(audio))
    if np.sum(magnitudes) > 0:
        centroid = np.sum(freqs * magnitudes) / np.sum(magnitudes)
    else:
        centroid = 0.0
    # Zero‑crossing rate
    zcr = np.mean(np.abs(np.diff(np.sign(audio)))) / 2.0
    return {
        'energy': energy,
        'pitch_mean': pitch_mean,
        'pitch_std': pitch_std,
        'spectral_centroid': centroid,
        'zcr': zcr
    }

def get_keywords(text):
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    filtered = [w for w in words if w not in STOPWORDS and len(w) > 2]
    freq = Counter(filtered)
    return json.dumps([w for w, _ in freq.most_common(5)])

def count_proper_nouns(text):
    words = text.split()
    count = 0
    for i, w in enumerate(words):
        if i > 0 and w and w[0].isupper():
            count += 1
    return count

def has_numbers(text):
    return 1 if re.search(r'\d', text) else 0

def compute_speaking_rate(text, duration_sec):
    words = len(text.split())
    return words / duration_sec if duration_sec > 0 else 0.0

def compute_vagueness(text, sentiment, pitch_std, keywords_json, proper_nouns, has_num):
    vagueness = 1.0
    keywords = json.loads(keywords_json)
    if len(keywords) <= 1:
        vagueness += 0.5
    elif len(keywords) >= 3:
        vagueness -= 0.3
    wc = len(text.split())
    if wc <= 5:
        vagueness += 0.3
    elif wc > 20:
        vagueness -= 0.2
    if abs(sentiment) < 0.2:
        vagueness += 0.3
    elif abs(sentiment) > 0.7:
        vagueness -= 0.2
    if pitch_std < 10:
        vagueness += 0.2
    else:
        vagueness -= 0.1
    vagueness -= 0.2 * proper_nouns
    if has_num:
        vagueness -= 0.3
    return max(0.0, min(2.0, vagueness))

def upgrade_all():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Get ALL utterances (ignore version)
    c.execute("SELECT uuid, file_path, start_ms, end_ms, text, sentiment FROM utterances")
    rows = c.fetchall()
    total = len(rows)
    print(f"🔄 Processing {total} utterances...")
    for idx, (uuid, fpath, start, end, text, sentiment) in enumerate(rows, 1):
        print(f"  [{idx}/{total}] {uuid[:8]} ...", end=' ', flush=True)
        audio, sr = load_segment(fpath, start, end)
        if audio is None or len(audio) < sr * 0.1:
            print("⚠️ skip (too short/load error)")
            continue
        pros = compute_prosody(audio, sr)
        if pros is None:
            print("⚠️ skip (prosody failed)")
            continue
        duration_sec = (end - start) / 1000.0
        speaking_rate = compute_speaking_rate(text, duration_sec)
        keywords = get_keywords(text)
        proper = count_proper_nouns(text)
        has_num = has_numbers(text)
        # Recompute vagueness using all features
        vagueness = compute_vagueness(text, sentiment or 0.0, pros['pitch_std'],
                                      keywords, proper, has_num)
        # Determine layer
        if vagueness >= 1.5:
            layer = 1
        elif vagueness >= 0.8:
            layer = 2
        else:
            layer = 3
        # Update DB
        c.execute("""UPDATE utterances SET
            pitch_mean = ?,
            pitch_std = ?,
            energy_mean = ?,
            speaking_rate = ?,
            spectral_centroid = ?,
            zcr = ?,
            keywords = ?,
            proper_nouns = ?,
            has_numbers = ?,
            vagueness = ?,
            layer = ?,
            feature_version = ?
            WHERE uuid = ?""",
            (pros['pitch_mean'], pros['pitch_std'], pros['energy'],
             speaking_rate, pros['spectral_centroid'], pros['zcr'],
             keywords, proper, has_num, vagueness, layer, NEW_VERSION, uuid))
        print(f"✅ vag={vagueness:.1f} layer={layer}")
    conn.commit()
    conn.close()
    print("✅ Upgrade complete (version", NEW_VERSION, ")")

if __name__ == "__main__":
    upgrade_all()
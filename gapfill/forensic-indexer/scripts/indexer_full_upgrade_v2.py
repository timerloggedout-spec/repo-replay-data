#!/usr/bin/env python3
"""Upgrade all utterances: extract prosody via ffmpeg + scipy,
   compute global word frequencies (Zipf), and re-score vagueness.
   Version 3.
"""
import os, sys, sqlite3, json, re, subprocess, tempfile, shutil
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.io import wavfile

PROJECT = os.path.expanduser("~/forensic-indexer")
DB = f"{PROJECT}/data/vault.db"
TMP = f"{PROJECT}/tmp"
os.makedirs(TMP, exist_ok=True)
NEW_VERSION = 3

# Stopwords
STOPWORDS = {
    'i','you','he','she','it','we','they','me','him','her','us','them',
    'my','your','his','her','our','their','a','an','the','and','or','but',
    'so','for','nor','on','at','to','by','in','of','with','without','about',
    'like','just','so','then','now','yeah','okay','uh','um','hmm','oh',
    'well','really','very','actually','gonna','wanna','got','get','let',
    'see','say','go','come','look','know','think','mean','want','need'
}

def extract_segment_ffmpeg(file_path, start_ms, end_ms, out_wav):
    """Use ffmpeg to extract segment to a WAV file."""
    start = start_ms / 1000.0
    duration = (end_ms - start_ms) / 1000.0
    if duration < 0.1:
        return False
    cmd = [
        'ffmpeg', '-y',
        '-i', file_path,
        '-ss', str(start),
        '-t', str(duration),
        '-ac', '1', '-ar', '16000',
        out_wav
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)
        return True
    except:
        return False

def compute_prosody_from_wav(wav_path):
    """Load WAV and compute pitch, energy, centroid, zcr."""
    sr, audio = wavfile.read(wav_path)
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float32) / 2147483648.0
    if len(audio) < sr * 0.1:
        return None
    # RMS energy
    energy = np.sqrt(np.mean(audio**2))
    # Pitch via FFT peak 50-300 Hz
    fft = np.abs(rfft(audio))
    freqs = rfftfreq(len(audio), 1/sr)
    mask = (freqs >= 50) & (freqs <= 300)
    if np.any(mask):
        pitch_mean = freqs[mask][np.argmax(fft[mask])]
    else:
        pitch_mean = 0.0
    # Pitch std (frame-based)
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
    # ZCR
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
    filtered = [w for w in words if w not in STOPWORDS and len(w)>2]
    freq = Counter(filtered)
    return json.dumps([w for w, _ in freq.most_common(5)])

def count_proper_nouns(text):
    words = text.split()
    return sum(1 for i, w in enumerate(words) if i>0 and w and w[0].isupper())

def has_numbers(text):
    return 1 if re.search(r'\d', text) else 0

def compute_speaking_rate(text, duration_sec):
    if duration_sec <= 0:
        return 0.0
    return len(text.split()) / duration_sec

def compute_vagueness(text, sentiment, pitch_std, keywords_json, proper_nouns, has_num, word_rarity_score):
    """word_rarity_score = average inverse frequency (lower = more common = more vague)"""
    vagueness = 1.0
    # Keywords
    keywords = json.loads(keywords_json)
    if len(keywords) <= 1:
        vagueness += 0.5
    elif len(keywords) >= 3:
        vagueness -= 0.3
    # Word count
    wc = len(text.split())
    if wc <= 5:
        vagueness += 0.3
    elif wc > 20:
        vagueness -= 0.2
    # Sentiment
    if abs(sentiment) < 0.2:
        vagueness += 0.3
    elif abs(sentiment) > 0.7:
        vagueness -= 0.2
    # Pitch monotony
    if pitch_std < 10:
        vagueness += 0.2
    else:
        vagueness -= 0.1
    # Proper nouns
    vagueness -= 0.2 * proper_nouns
    # Numbers
    if has_num:
        vagueness -= 0.3
    # Word rarity: higher rarity = more specific → lower vagueness
    if word_rarity_score < 0.001:  # very common words → vague
        vagueness += 0.3
    elif word_rarity_score > 0.01:  # rare words → specific
        vagueness -= 0.3
    return max(0.0, min(2.0, vagueness))

def upgrade_all():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # ---- 1. Compute global word frequencies (Zipf baseline) ----
    c.execute("SELECT text FROM utterances WHERE text IS NOT NULL")
    texts = [row[0] for row in c.fetchall()]
    all_words = []
    for t in texts:
        words = re.findall(r'\b[a-zA-Z]{2,}\b', t.lower())
        all_words.extend(words)
    word_freq = Counter(all_words)
    total_words = sum(word_freq.values())
    # inverse frequency per word (rarity)
    inv_freq = {w: 1.0 / (freq + 1) for w, freq in word_freq.items()}
    print(f"📊 Global word count: {total_words}, unique: {len(word_freq)}")

    # ---- 2. Process each utterance ----
    c.execute("SELECT uuid, file_path, start_ms, end_ms, text, sentiment FROM utterances")
    rows = c.fetchall()
    total = len(rows)
    print(f"🔄 Processing {total} utterances...")
    for idx, (uuid, fpath, start, end, text, sentiment) in enumerate(rows, 1):
        print(f"  [{idx}/{total}] {uuid[:8]} ...", end=' ', flush=True)

        # Text-based features (always compute)
        keywords = get_keywords(text)
        proper = count_proper_nouns(text)
        has_num = has_numbers(text)
        duration_sec = (end - start) / 1000.0
        speaking_rate = compute_speaking_rate(text, duration_sec)

        # Word rarity score for this utterance: average of inverse frequencies of its words
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        if words:
            rarity = np.mean([inv_freq.get(w, 0.0) for w in words])
        else:
            rarity = 0.0

        # ---- Audio features (via ffmpeg) ----
        audio_feats = None
        temp_wav = os.path.join(TMP, f"seg_{uuid[:8]}.wav")
        if os.path.exists(fpath):
            if extract_segment_ffmpeg(fpath, start, end, temp_wav):
                audio_feats = compute_prosody_from_wav(temp_wav)
            # clean up
            if os.path.exists(temp_wav):
                os.unlink(temp_wav)
        else:
            print("⚠️ file not found", end=' ')

        if audio_feats is None:
            # fallback: use defaults
            pitch_mean = 0.0
            pitch_std = 0.0
            energy = 0.0
            centroid = 0.0
            zcr = 0.0
            print("⚠️ audio skipped", end=' ')
        else:
            pitch_mean = audio_feats['pitch_mean']
            pitch_std = audio_feats['pitch_std']
            energy = audio_feats['energy']
            centroid = audio_feats['spectral_centroid']
            zcr = audio_feats['zcr']
            print("🎵", end=' ')

        # Compute vagueness
        vagueness = compute_vagueness(text, sentiment or 0.0, pitch_std,
                                      keywords, proper, has_num, rarity)
        # Layer
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
            (pitch_mean, pitch_std, energy, speaking_rate, centroid, zcr,
             keywords, proper, has_num, vagueness, layer, NEW_VERSION, uuid))
        print(f"✅ vag={vagueness:.1f} layer={layer}")

    conn.commit()
    conn.close()
    print("✅ Upgrade complete (version", NEW_VERSION, ")")

if __name__ == "__main__":
    upgrade_all()
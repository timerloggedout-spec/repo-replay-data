#!/usr/bin/env python3
"""
Batch transcribe + word‑level feature extraction.
- Convert .m4a -> 16kHz mono WAV.
- Run whisper.cpp small to get .txt, .vtt (fallback).
- Parse words and timestamps.
- Extract pitch, energy, spectral centroid, zcr per word (all floats).
- Insert utterances and words into DB.
- Clean up temp files.
"""
import os, sys, sqlite3, subprocess, uuid, time, glob
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.fft import rfft, rfftfreq

PROJECT = os.path.expanduser("~/forensic-indexer")
DB = f"{PROJECT}/data/vault.db"
WHISPER_BIN = f"{PROJECT}/whisper.cpp/build/bin/whisper-cli"
MODEL = f"{PROJECT}/whisper.cpp/models/ggml-small.bin"
TMP = f"{PROJECT}/tmp"
REC_DIR = "/data/data/com.termux/files/home/storage/shared/Audio/Recordings"
LOG_FILE = f"{PROJECT}/batch.log"
os.makedirs(TMP, exist_ok=True)

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    full = f"[{ts}] {msg}"
    print(full)
    with open(LOG_FILE, 'a') as f:
        f.write(full + "\n")

def get_duration(m4a_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', m4a_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        dur = float(result.stdout.strip()) * 1000
        return int(dur)
    except:
        return 0

def extract_word_features(audio, sr, start_ms, end_ms):
    """Return dict of pitch, energy, centroid, zcr as floats."""
    start = int(start_ms * sr / 1000)
    end = int(end_ms * sr / 1000)
    seg = audio[start:end]
    if len(seg) < 10:
        return {'pitch': 0.0, 'energy': 0.0, 'centroid': 0.0, 'zcr': 0.0}
    energy = float(np.sqrt(np.mean(seg**2)))
    fft = np.abs(rfft(seg))
    freqs = rfftfreq(len(seg), 1/sr)
    mask = (freqs >= 50) & (freqs <= 300)
    pitch = float(freqs[mask][np.argmax(fft[mask])]) if np.any(mask) else 0.0
    magnitudes = np.abs(rfft(seg))
    centroid = float(np.sum(freqs * magnitudes) / (np.sum(magnitudes) + 1e-6))
    zcr = float(np.mean(np.abs(np.diff(np.sign(seg)))) / 2.0)
    return {'pitch': pitch, 'energy': energy, 'centroid': centroid, 'zcr': zcr}

def parse_vtt(vtt_path):
    segments = []
    with open(vtt_path, 'r') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        if '-->' in lines[i]:
            times = lines[i].strip().split(' --> ')
            def to_ms(t):
                h, m, s = t[0], t[1], t[2]
                return int(h)*3600000 + int(m)*60000 + int(float(s)*1000)
            start_ms = to_ms(times[0].replace('.', ':').split(':'))
            end_ms = to_ms(times[1].replace('.', ':').split(':'))
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() != '':
                text_lines.append(lines[i].strip())
                i += 1
            text = ' '.join(text_lines).strip()
            if text:
                segments.append((start_ms, end_ms, text))
        i += 1
    return segments

def process_file(m4a_path):
    base = os.path.basename(m4a_path).replace('.m4a', '')
    wav_path = os.path.join(TMP, f"{base}.wav")
    txt_path = wav_path + ".txt"
    wts_path = wav_path + ".wts"
    vtt_path = wav_path + ".vtt"

    log(f"Processing: {m4a_path}")

    # 1. Convert to WAV
    subprocess.run(['ffmpeg', '-y', '-i', m4a_path, '-ar', '16000', '-ac', '1', wav_path],
                   check=True, capture_output=True)

    # 2. Run whisper-cli
    subprocess.run([WHISPER_BIN, '-m', MODEL, '-f', wav_path, '-otxt', '-owts', '-ovtt'],
                   check=True, capture_output=True, timeout=600)

    # 3. Parse words
    words = []
    if os.path.exists(wts_path) and os.path.getsize(wts_path) > 0:
        with open(wts_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 3: continue
                start = float(parts[0]) * 1000
                end = float(parts[1]) * 1000
                word = ' '.join(parts[2:])
                words.append((start, end, word))
        log(f"  📝 Parsed {len(words)} words from .wts")
    elif os.path.exists(vtt_path):
        segments = parse_vtt(vtt_path)
        for start_ms, end_ms, text in segments:
            word_list = text.split()
            if not word_list: continue
            dur_per_word = (end_ms - start_ms) / len(word_list)
            for i, w in enumerate(word_list):
                w_start = start_ms + i * dur_per_word
                w_end = w_start + dur_per_word
                words.append((w_start, w_end, w))
        log(f"  📝 Parsed {len(words)} words from .vtt (approx)")
    else:
        log(f"  ⚠️ No word timestamps; using full text as one utterance")
        with open(txt_path, 'r') as f:
            full_text = f.read().strip()
        dur_ms = get_duration(m4a_path)
        words = [(0, dur_ms, full_text)]

    if not words:
        log(f"  ❌ No words found for {base}")
        return

    # 4. Load audio for feature extraction
    sr, audio_int16 = wavfile.read(wav_path)
    audio_float = audio_int16.astype(np.float32) / 32768.0

    # 5. Group into utterances by gaps > 1.0s
    utterances = []
    current = [words[0]]
    for i in range(1, len(words)):
        gap = words[i][0] - words[i-1][1]
        if gap > 1000:
            utterances.append(current)
            current = [words[i]]
        else:
            current.append(words[i])
    if current:
        utterances.append(current)

    log(f"  🗣️ Found {len(utterances)} utterances")

    # 6. Insert into DB
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('DELETE FROM words WHERE utterance_uuid IN (SELECT uuid FROM utterances WHERE file_path = ?)', (m4a_path,))
    c.execute('DELETE FROM utterances WHERE file_path = ?', (m4a_path,))

    for utt_words in utterances:
        start_ms = utt_words[0][0]
        end_ms = utt_words[-1][1]
        text = ' '.join([w[2] for w in utt_words])
        uid = str(uuid.uuid4())
        c.execute('INSERT INTO utterances (uuid, file_path, start_ms, end_ms, text, speaker, feature_version) VALUES (?, ?, ?, ?, ?, ?, ?)',
                  (uid, m4a_path, start_ms, end_ms, text, 'UNKNOWN', 0))
        # Insert words with features
        for start, end, word in utt_words:
            feats = extract_word_features(audio_float, sr, start, end)
            c.execute('''INSERT INTO words
                         (utterance_uuid, word_text, start_ms, end_ms,
                          pitch_mean, pitch_std, energy_mean, spectral_centroid, zcr, speaking_rate)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (uid, word, start, end,
                       feats['pitch'], 0.0, feats['energy'], feats['centroid'], feats['zcr'], 0.0))
    conn.commit()
    conn.close()

    # Clean up
    for f in [wav_path, txt_path, wts_path, vtt_path]:
        if os.path.exists(f):
            os.unlink(f)

    log(f"  ✅ Inserted {len(utterances)} utterances.")

def main():
    files = sorted(glob.glob(os.path.join(REC_DIR, '*.m4a')))
    log(f"🔍 Found {len(files)} files to process.")
    for f in files:
        process_file(f)
    log("✅ All files processed.")

if __name__ == '__main__':
    main()
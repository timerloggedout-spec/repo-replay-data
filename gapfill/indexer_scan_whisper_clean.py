#!/usr/bin/env python3
# indexer_scan_whisper_clean.py – Pure whisper, no numba (with dummy numba)

import os, sqlite3, json, hashlib, argparse, datetime, uuid, subprocess
from pathlib import Path
from collections import Counter

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import torch
import torchaudio
import numpy as np
import scipy.signal
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import whisper

# ------------------ CONFIG ------------------
PROJECT_ROOT = os.path.expanduser("~/forensic-indexer")
DB_PATH = os.path.join(PROJECT_ROOT, "data/vault.db")
ORIG_DIR = os.path.expanduser("~/storage/shared/Audio/Recordings")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

sent_analyzer = SentimentIntensityAnalyzer()

# Stopword list (common English stopwords)
STOPWORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd",
    'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers',
    'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
    'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having',
    'do', 'does', 'did', 'doing', 'will', 'would', 'shall', 'should', 'may', 'might', 'must', 'can', 'could',
    'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for',
    'with', 'without', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further',
    'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few',
    'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
    'too', 'very', 'just', 'but'
}

# ------------------ DB SCHEMA ------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS files (
                 file_path TEXT PRIMARY KEY,
                 origin_cid TEXT,
                 sha256 TEXT,
                 duration_sec REAL,
                 file_datetime INTEGER,
                 file_size INTEGER,
                 tags TEXT,
                 metadata TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS utterances (
                 uuid TEXT PRIMARY KEY,
                 file_path TEXT,
                 start_ms INTEGER,
                 end_ms INTEGER,
                 speaker TEXT,
                 text TEXT,
                 sentiment REAL,
                 pitch_mean REAL,
                 pitch_std REAL,
                 energy_mean REAL,
                 vagueness REAL,
                 ner_entities TEXT,
                 keywords TEXT,
                 layer INTEGER DEFAULT 1,
                 release_time INTEGER DEFAULT 0,
                 snippet_cid TEXT,
                 tags TEXT
                 )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_utt_file ON utterances(file_path)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_utt_time ON utterances(start_ms)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_utt_vague ON utterances(vagueness)')
    conn.commit()
    conn.close()

# ------------------ PROCESS ONE FILE ------------------
def process_file(file_path, skip_if_exists=True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if skip_if_exists:
        cur = c.execute('SELECT COUNT(*) FROM utterances WHERE file_path=?', (file_path,))
        if cur.fetchone()[0] > 0:
            print(f"⏭️ Skipping {file_path} – already indexed.")
            conn.close()
            return

    print(f"📂 Indexing: {file_path}")

    # File metadata
    basename = Path(file_path).stem
    try:
        dt = datetime.datetime.strptime(basename, "%Y%m%d_%H%M%S")
        file_ts = int(dt.timestamp())
    except:
        file_ts = int(os.path.getmtime(file_path))
    file_size = os.path.getsize(file_path)
    with open(file_path, 'rb') as f:
        sha256_origin = hashlib.sha256(f.read()).hexdigest()

    dur_str = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]).decode().strip()
    duration_sec = float(dur_str) if dur_str else 0.0

    c.execute('''INSERT OR REPLACE INTO files
                 (file_path, origin_cid, sha256, duration_sec, file_datetime, file_size, tags, metadata)
                 VALUES (?,?,?,?,?,?,?,?)''',
              (file_path, None, sha256_origin, duration_sec, file_ts, file_size, '[]', '{}'))

    # Load audio (whisper's loader)
    audio = whisper.load_audio(file_path)
    print("  🧠 Transcribing with whisper tiny...")
    model = whisper.load_model("tiny", device="cpu")
    result = model.transcribe(audio, word_timestamps=True)
    segments = result["segments"]

    # Load audio for prosody via torchaudio (16kHz mono)
    waveform, sr = torchaudio.load(file_path)
    if sr != 16000:
        resampler = torchaudio.transforms.Resample(sr, 16000)
        waveform = resampler(waveform)
        sr = 16000
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    audio_np = waveform.squeeze().numpy()

    inserted = 0
    for seg in segments:
        start_s = seg['start']; end_s = seg['end']
        start_idx = int(start_s * sr); end_idx = int(end_s * sr)
        seg_samples = audio_np[start_idx:end_idx]
        if len(seg_samples) < 100:
            continue

        # RMS energy
        rms = np.sqrt(np.mean(seg_samples**2)) if len(seg_samples)>0 else 0.0
        energy_mean = rms

        # Pitch via FFT
        try:
            from scipy.fft import rfft, rfftfreq
            fft = rfft(seg_samples)
            freqs = rfftfreq(len(seg_samples), 1/sr)
            mag = np.abs(fft)
            band = (freqs >= 50) & (freqs <= 300)
            if np.any(band):
                peak_idx = np.argmax(mag[band])
                pitch_hz = freqs[band][peak_idx]
            else:
                pitch_hz = 0.0
        except:
            pitch_hz = 0.0
        pitch_mean = pitch_hz
        pitch_std = 0.0

        text = seg['text'].strip()
        if not text:
            continue

        # Sentiment
        sentiment = sent_analyzer.polarity_scores(text)['compound']

        # Keywords
        words = text.lower().split()
        keywords = [w for w in words if w not in STOPWORDS and len(w) > 2]
        top_keywords = [k for k, _ in Counter(keywords).most_common(5)]
        keywords_json = json.dumps(top_keywords)

        word_count = len(words)
        named_entities = 0

        # Vagueness
        vagueness = 0.0
        if len(top_keywords) <= 1: vagueness += 1.0
        elif len(top_keywords) >= 3: vagueness -= 0.5
        if word_count <= 5: vagueness += 0.5
        elif word_count > 20: vagueness -= 0.3
        if abs(sentiment) < 0.2: vagueness += 0.5
        elif abs(sentiment) > 0.7: vagueness -= 0.3
        if pitch_std < 20: vagueness += 0.3
        else: vagueness -= 0.2
        vagueness = max(0.0, min(2.0, vagueness))

        utt_uuid = str(uuid.uuid4())
        c.execute('''INSERT INTO utterances
                     (uuid, file_path, start_ms, end_ms, speaker, text, sentiment,
                      pitch_mean, pitch_std, energy_mean, vagueness,
                      ner_entities, keywords, layer, release_time, snippet_cid, tags)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (utt_uuid, file_path, int(start_s*1000), int(end_s*1000),
                   "UNKNOWN", text, sentiment,
                   pitch_mean, pitch_std, energy_mean, vagueness,
                   '[]', keywords_json, 1, 0, None, '[]'))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"  ✅ Inserted {inserted} utterances from {file_path}")

# ------------------ MAIN ------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file")
    parser.add_argument("--dir", default=None)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true", default=True)
    args = parser.parse_args()
    init_db()
    if args.file:
        process_file(args.file, skip_if_exists=args.resume)
    elif args.dir:
        files = sorted(Path(args.dir).glob("*.m4a"))
        if args.limit:
            files = files[:args.limit]
        for f in files:
            process_file(str(f), skip_if_exists=args.resume)
    else:
        print(f"📍 Scanning first 5 files from {ORIG_DIR}")
        files = sorted(Path(ORIG_DIR).glob("*.m4a"))[:5]
        for f in files:
            process_file(str(f), skip_if_exists=True)

if __name__ == "__main__":
    main()
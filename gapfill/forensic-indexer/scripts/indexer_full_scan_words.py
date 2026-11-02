#!/usr/bin/env python3
"""
Full scan: transcribe with word timestamps, extract prosodic features for each word,
store words in a separate table.
"""
import os, sys, sqlite3, json, re, hashlib, tempfile, subprocess
from pathlib import Path
import torch
import torchaudio
import numpy as np
from scipy.fft import rfft, rfftfreq

PROJECT = os.path.expanduser("~/forensic-indexer")
DB = f"{PROJECT}/data/vault.db"
TMP = f"{PROJECT}/tmp"
os.makedirs(TMP, exist_ok=True)

# Whisper
import whisper
model = whisper.load_model("tiny")  # or "base" if you have RAM

def compute_frame_features(audio, sr, frame_ms=25, hop_ms=10):
    """Return arrays: times (ms), pitch, energy, centroid, zcr per frame."""
    frame_len = int(frame_ms * sr / 1000)
    hop_len = int(hop_ms * sr / 1000)
    n_frames = (len(audio) - frame_len) // hop_len + 1
    times = []
    pitches = []
    energies = []
    centroids = []
    zcrs = []
    for i in range(n_frames):
        start = i * hop_len
        end = start + frame_len
        frame = audio[start:end]
        times.append(start * 1000 / sr)  # ms
        # energy
        energy = np.sqrt(np.mean(frame**2))
        energies.append(energy)
        # pitch: FFT peak 50-300 Hz
        fft = np.abs(rfft(frame))
        freqs = rfftfreq(len(frame), 1/sr)
        mask = (freqs >= 50) & (freqs <= 300)
        if np.any(mask):
            pitch = freqs[mask][np.argmax(fft[mask])]
        else:
            pitch = 0.0
        pitches.append(pitch)
        # spectral centroid
        magnitudes = np.abs(rfft(frame))
        if np.sum(magnitudes) > 0:
            centroid = np.sum(freqs * magnitudes) / np.sum(magnitudes)
        else:
            centroid = 0.0
        centroids.append(centroid)
        # zcr
        zcr = np.mean(np.abs(np.diff(np.sign(frame)))) / 2.0
        zcrs.append(zcr)
    return times, pitches, energies, centroids, zcrs

def process_file(file_path):
    print(f"📂 Indexing: {file_path}")
    # Transcribe with word timestamps
    result = model.transcribe(file_path, word_timestamps=True, fp16=False)
    segments = result['segments']
    if not segments:
        print("  ⚠️ No transcription")
        return

    # Load audio for feature extraction
    try:
        waveform, sr = torchaudio.load(file_path)
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        audio = waveform.squeeze(0).numpy()
    except Exception as e:
        print(f"  ⚠️ Failed to load audio: {e}")
        return

    # Compute frame features (once per file)
    times, pitches, energies, centroids, zcrs = compute_frame_features(audio, sr)
    # Convert to numpy for interpolation
    times_np = np.array(times)
    pitches_np = np.array(pitches)
    energies_np = np.array(energies)
    centroids_np = np.array(centroids)
    zcrs_np = np.array(zcrs)

    # Connect to DB
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # For each segment (utterance)
    for seg in segments:
        seg_start = seg['start'] * 1000
        seg_end = seg['end'] * 1000
        seg_text = seg['text'].strip()
        # Insert utterance (if not exists) - we'll use upsert
        c.execute("SELECT uuid FROM utterances WHERE file_path=? AND start_ms=? AND end_ms=?",
                  (file_path, seg_start, seg_end))
        row = c.fetchone()
        if row:
            uuid = row[0]
            # Update text? maybe keep
            c.execute("UPDATE utterances SET text=? WHERE uuid=?", (seg_text, uuid))
        else:
            import uuid as uuidlib
            uuid = str(uuidlib.uuid4())
            c.execute("""INSERT INTO utterances (uuid, file_path, start_ms, end_ms, text, speaker, feature_version)
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                      (uuid, file_path, seg_start, seg_end, seg_text, "UNKNOWN", 0))
        # Now insert words
        for word_info in seg.get('words', []):
            word = word_info['word'].strip()
            w_start = word_info['start'] * 1000
            w_end = word_info['end'] * 1000
            # Average features over frames within [w_start, w_end]
            mask = (times_np >= w_start) & (times_np <= w_end)
            if np.any(mask):
                pitch_mean = np.mean(pitches_np[mask]) if np.any(mask) else 0.0
                pitch_std = np.std(pitches_np[mask]) if np.any(mask) else 0.0
                energy_mean = np.mean(energies_np[mask]) if np.any(mask) else 0.0
                centroid_mean = np.mean(centroids_np[mask]) if np.any(mask) else 0.0
                zcr_mean = np.mean(zcrs_np[mask]) if np.any(mask) else 0.0
            else:
                # fallback
                pitch_mean = 0.0
                pitch_std = 0.0
                energy_mean = 0.0
                centroid_mean = 0.0
                zcr_mean = 0.0
            # Speaking rate: words per second around this word? Approx: 1 / (duration in sec)
            duration_sec = (w_end - w_start) / 1000.0
            speaking_rate = 1.0 / duration_sec if duration_sec > 0 else 0.0
            # Insert word
            c.execute("""INSERT INTO words
                         (utterance_uuid, word_text, start_ms, end_ms,
                          pitch_mean, pitch_std, energy_mean, spectral_centroid, zcr, speaking_rate)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (uuid, word, w_start, w_end,
                       pitch_mean, pitch_std, energy_mean, centroid_mean, zcr_mean, speaking_rate))
    conn.commit()
    conn.close()
    print(f"  ✅ Inserted {len(segments)} utterances and words.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Single file to process")
    parser.add_argument("--limit", type=int, help="Process first N files")
    args = parser.parse_args()

    if args.file:
        process_file(args.file)
    else:
        # Scan all files in the Recordings directory
        rec_dir = "/data/data/com.termux/files/home/storage/shared/Audio/Recordings"
        files = sorted([os.path.join(rec_dir, f) for f in os.listdir(rec_dir) if f.endswith('.m4a')])
        if args.limit:
            files = files[:args.limit]
        for f in files:
            process_file(f)
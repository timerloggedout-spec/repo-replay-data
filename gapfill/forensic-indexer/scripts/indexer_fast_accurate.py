#!/usr/bin/env python3
"""
Fast & accurate scanner:
- VAD (webrtcvad) splits audio into speech segments.
- Whisper (base/small) transcribes each segment with word timestamps.
- Prosodic features extracted from WAV via scipy.
- Stores utterances and words in DB.
"""
import os, sys, sqlite3, json, tempfile, subprocess
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.fft import rfft, rfftfreq
import webrtcvad
from pydub import AudioSegment
import whisper

PROJECT = os.path.expanduser("~/forensic-indexer")
DB = f"{PROJECT}/data/vault.db"
TMP = f"{PROJECT}/tmp"
os.makedirs(TMP, exist_ok=True)

# Load Whisper model once (choose 'base' or 'small')
MODEL_NAME = "base"  # "small" for better accuracy (uses ~2GB RAM)
model = whisper.load_model(MODEL_NAME)

# VAD parameters
VAD_MODE = 1  # Aggressiveness: 0-3 (1 is moderate)
FRAME_DURATION_MS = 30  # Must be 10, 20, or 30 ms

def compute_frame_features(audio, sr):
    """Compute pitch, energy, centroid, zcr per word (average over frames)."""
    # Use frame-level features then average over word window
    # We'll compute per word in the caller, so we'll provide a function to get features for a given time window
    pass  # We'll implement inline per word

def extract_word_features(audio, sr, start_ms, end_ms):
    """Extract features from the audio segment [start_ms, end_ms]."""
    start = int(start_ms * sr / 1000)
    end = int(end_ms * sr / 1000)
    segment = audio[start:end]
    if len(segment) < 10:
        return {'pitch': 0, 'energy': 0, 'centroid': 0, 'zcr': 0}
    # Energy
    energy = np.sqrt(np.mean(segment**2))
    # Pitch: FFT peak 50-300 Hz
    fft = np.abs(rfft(segment))
    freqs = rfftfreq(len(segment), 1/sr)
    mask = (freqs >= 50) & (freqs <= 300)
    if np.any(mask):
        pitch = freqs[mask][np.argmax(fft[mask])]
    else:
        pitch = 0.0
    # Spectral centroid
    magnitudes = np.abs(rfft(segment))
    if np.sum(magnitudes) > 0:
        centroid = np.sum(freqs * magnitudes) / np.sum(magnitudes)
    else:
        centroid = 0.0
    # ZCR
    zcr = np.mean(np.abs(np.diff(np.sign(segment)))) / 2.0
    return {'pitch': pitch, 'energy': energy, 'centroid': centroid, 'zcr': zcr}

def process_file(file_path):
    print(f"📂 Indexing: {file_path}")
    # Convert m4a to WAV (16kHz mono) using ffmpeg
    wav_path = os.path.join(TMP, f"temp_{os.path.basename(file_path)}.wav")
    cmd = ['ffmpeg', '-y', '-i', file_path, '-ac', '1', '-ar', '16000', wav_path]
    subprocess.run(cmd, check=True, capture_output=True)
    
    # Load audio for VAD and feature extraction
    sr, audio_int16 = wavfile.read(wav_path)
    if audio_int16.dtype != np.int16:
        audio_int16 = audio_int16.astype(np.int16)
    audio_float = audio_int16.astype(np.float32) / 32768.0  # normalized

    # VAD: split into speech segments
    vad = webrtcvad.Vad(VAD_MODE)
    # We process in frames of 30ms
    frame_bytes = int(FRAME_DURATION_MS * sr / 1000) * 2  # 16-bit = 2 bytes per sample
    sample_count = int(FRAME_DURATION_MS * sr / 1000)
    # Convert to bytes for VAD
    audio_bytes = audio_int16.tobytes()
    # Get speech segments as (start_ms, end_ms)
    segments = []
    is_speech = False
    start_frame = 0
    for i in range(0, len(audio_int16) - sample_count + 1, sample_count):
        frame = audio_int16[i:i+sample_count]
        if len(frame) != sample_count:
            break
        is_speech_now = vad.is_speech(frame.tobytes(), sr)
        if is_speech_now and not is_speech:
            is_speech = True
            start_frame = i
        elif not is_speech_now and is_speech:
            is_speech = False
            start_ms = int(start_frame * 1000 / sr)
            end_ms = int(i * 1000 / sr)
            if end_ms - start_ms > 300:  # at least 300ms
                segments.append((start_ms, end_ms))
    # If ending with speech
    if is_speech:
        start_ms = int(start_frame * 1000 / sr)
        end_ms = int(len(audio_int16) * 1000 / sr)
        if end_ms - start_ms > 300:
            segments.append((start_ms, end_ms))
    
    print(f"  🗣️ VAD found {len(segments)} speech segments")

    if not segments:
        print("  ⚠️ No speech detected")
        os.unlink(wav_path)
        return

    # Transcribe each segment and extract words
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    for start_ms, end_ms in segments:
        # Extract segment audio for Whisper (we'll use the WAV file and ffmpeg to cut)
        seg_wav = os.path.join(TMP, f"seg_{os.path.basename(file_path)}_{start_ms}_{end_ms}.wav")
        cmd = ['ffmpeg', '-y', '-ss', str(start_ms/1000.0), '-to', str(end_ms/1000.0), '-i', wav_path, '-ac', '1', '-ar', '16000', seg_wav]
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Transcribe segment
        result = model.transcribe(seg_wav, word_timestamps=True, fp16=False, language='en', temperature=0.0)
        if not result['segments']:
            os.unlink(seg_wav)
            continue
        
        # Insert utterance
        text = result['text'].strip()
        import uuid
        uid = str(uuid.uuid4())
        c.execute("""INSERT INTO utterances (uuid, file_path, start_ms, end_ms, text, speaker, feature_version)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (uid, file_path, start_ms, end_ms, text, "UNKNOWN", 0))
        
        # Extract words and features
        for seg in result['segments']:
            for word_info in seg.get('words', []):
                word = word_info['word'].strip()
                w_start = word_info['start'] * 1000
                w_end = word_info['end'] * 1000
                # Features from the original audio (float version)
                feats = extract_word_features(audio_float, sr, w_start, w_end)
                # Speaking rate: approximate words per second for this word
                dur_sec = (w_end - w_start) / 1000.0
                speaking_rate = 1.0 / dur_sec if dur_sec > 0 else 0.0
                c.execute("""INSERT INTO words
                             (utterance_uuid, word_text, start_ms, end_ms,
                              pitch_mean, pitch_std, energy_mean, spectral_centroid, zcr, speaking_rate)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (uid, word, w_start, w_end,
                           feats['pitch'], 0.0, feats['energy'], feats['centroid'], feats['zcr'], speaking_rate))
        
        # Clean up segment WAV
        os.unlink(seg_wav)
    
    conn.commit()
    conn.close()
    os.unlink(wav_path)
    print(f"  ✅ Inserted {len(segments)} utterances.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Single file to process")
    parser.add_argument("--limit", type=int, help="Process first N files")
    args = parser.parse_args()
    
    rec_dir = "/data/data/com.termux/files/home/storage/shared/Audio/Recordings"
    if args.file:
        process_file(args.file)
    else:
        files = sorted([os.path.join(rec_dir, f) for f in os.listdir(rec_dir) if f.endswith('.m4a')])
        if args.limit:
            files = files[:args.limit]
        for f in files:
            process_file(f)
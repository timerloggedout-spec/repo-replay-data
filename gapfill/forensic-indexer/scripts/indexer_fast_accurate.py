#!/usr/bin/env python3
"""
Fast & accurate scanner - with anti-hallucination settings.
- VAD_MODE=2 (balanced)
- Min segment duration 700ms
- Whisper: temperature=0.0, condition_on_previous_text=False, no_speech_threshold=0.6, logprob_threshold=-1.0
- Features extracted via scipy.
"""
import os, sys, sqlite3, json, tempfile, subprocess, uuid
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.fft import rfft, rfftfreq
import webrtcvad
import whisper

PROJECT = os.path.expanduser("~/forensic-indexer")
DB = f"{PROJECT}/data/vault.db"
TMP = f"{PROJECT}/tmp"
os.makedirs(TMP, exist_ok=True)

MODEL_NAME = "base"   # or "small"
model = whisper.load_model(MODEL_NAME)

VAD_MODE = 2          # 0-3 (2 = balanced)
FRAME_MS = 30
MIN_SEGMENT_MS = 700  # longer segments reduce hallucination

def extract_word_features(audio, sr, start_ms, end_ms):
    start = int(start_ms * sr / 1000)
    end = int(end_ms * sr / 1000)
    seg = audio[start:end]
    if len(seg) < 10:
        return {'pitch': 0.0, 'energy': 0.0, 'centroid': 0.0, 'zcr': 0.0}
    energy = np.sqrt(np.mean(seg**2))
    fft = np.abs(rfft(seg))
    freqs = rfftfreq(len(seg), 1/sr)
    mask = (freqs >= 50) & (freqs <= 300)
    pitch = freqs[mask][np.argmax(fft[mask])] if np.any(mask) else 0.0
    magnitudes = np.abs(rfft(seg))
    centroid = np.sum(freqs * magnitudes) / (np.sum(magnitudes) + 1e-6)
    zcr = np.mean(np.abs(np.diff(np.sign(seg)))) / 2.0
    return {'pitch': pitch, 'energy': energy, 'centroid': centroid, 'zcr': zcr}

def process_file(file_path):
    print(f"📂 Indexing: {file_path}")
    wav_path = os.path.join(TMP, f"temp_{os.path.basename(file_path)}.wav")
    subprocess.run(['ffmpeg', '-y', '-i', file_path, '-ac', '1', '-ar', '16000', wav_path],
                   check=True, capture_output=True)

    sr, audio_int16 = wavfile.read(wav_path)
    audio_int16 = audio_int16.astype(np.int16)
    audio_float = audio_int16.astype(np.float32) / 32768.0

    vad = webrtcvad.Vad(VAD_MODE)
    frame_len = int(FRAME_MS * sr / 1000)
    segments = []
    is_speech = False
    start_frame = 0
    for i in range(0, len(audio_int16) - frame_len + 1, frame_len):
        frame = audio_int16[i:i+frame_len]
        if len(frame) != frame_len:
            break
        is_speech_now = vad.is_speech(frame.tobytes(), sr)
        if is_speech_now and not is_speech:
            is_speech = True
            start_frame = i
        elif not is_speech_now and is_speech:
            is_speech = False
            start_ms = int(start_frame * 1000 / sr)
            end_ms = int(i * 1000 / sr)
            if end_ms - start_ms >= MIN_SEGMENT_MS:
                segments.append((start_ms, end_ms))
    if is_speech:
        start_ms = int(start_frame * 1000 / sr)
        end_ms = int(len(audio_int16) * 1000 / sr)
        if end_ms - start_ms >= MIN_SEGMENT_MS:
            segments.append((start_ms, end_ms))

    print(f"  🗣️ VAD found {len(segments)} speech segments")
    if not segments:
        os.unlink(wav_path)
        return

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    for start_ms, end_ms in segments:
        seg_wav = os.path.join(TMP, f"seg_{os.path.basename(file_path)}_{start_ms}_{end_ms}.wav")
        subprocess.run(['ffmpeg', '-y', '-ss', str(start_ms/1000.0), '-to', str(end_ms/1000.0),
                        '-i', wav_path, seg_wav], check=True, capture_output=True)

        # Transcribe with anti‑hallucination settings
        result = model.transcribe(
            seg_wav,
            word_timestamps=True,
            fp16=False,
            language='en',
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0
        )
        os.unlink(seg_wav)

        if not result['segments']:
            continue

        text = result['text'].strip()
        uid = str(uuid.uuid4())
        c.execute("""INSERT INTO utterances (uuid, file_path, start_ms, end_ms, text, speaker, feature_version)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (uid, file_path, start_ms, end_ms, text, "UNKNOWN", 0))

        for seg in result['segments']:
            for w_info in seg.get('words', []):
                word = w_info['word'].strip()
                w_start = w_info['start'] * 1000
                w_end = w_info['end'] * 1000
                feats = extract_word_features(audio_float, sr, w_start, w_end)
                dur = (w_end - w_start) / 1000.0
                speaking_rate = 1.0 / dur if dur > 0 else 0.0
                c.execute("""INSERT INTO words
                             (utterance_uuid, word_text, start_ms, end_ms,
                              pitch_mean, pitch_std, energy_mean, spectral_centroid, zcr, speaking_rate)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (uid, word, w_start, w_end,
                           feats['pitch'], 0.0, feats['energy'], feats['centroid'], feats['zcr'], speaking_rate))

    conn.commit()
    conn.close()
    os.unlink(wav_path)
    print(f"  ✅ Inserted {len(segments)} utterances.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Single file")
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
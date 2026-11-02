#!/usr/bin/env python3
"""
Speaker diarization + layer assignment (DB-only, no sklearn).
- Splits words into two speakers based on median pitch.
- Updates words.speaker.
- Aggregates per utterance: speaker counts, pitch range, energy range, sentiment, keyword rarity, etc.
- Computes vagueness and assigns layer (1=teaser, 2=partial, 3=full).
"""
import os, sys, sqlite3, json, re
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

PROJECT = os.path.expanduser("~/forensic-indexer")
DB = f"{PROJECT}/data/vault.db"
analyzer = SentimentIntensityAnalyzer()

STOPWORDS = {'i','you','he','she','it','we','they','me','him','her','us','them','my','your','his','her','our','their',
             'a','an','the','and','or','but','so','for','nor','on','at','to','by','in','of','with','without','about',
             'like','just','so','then','now','yeah','okay','uh','um','hmm','oh','well','really','very','actually'}

def get_keywords(text):
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    filtered = [w for w in words if w not in STOPWORDS and len(w)>2]
    from collections import Counter
    freq = Counter(filtered)
    return json.dumps([w for w, _ in freq.most_common(5)])

def count_proper_nouns(text):
    words = text.split()
    return sum(1 for i, w in enumerate(words) if i>0 and w and w[0].isupper())

def has_numbers(text):
    return 1 if re.search(r'\d', text) else 0

def assign_speakers(conn):
    c = conn.cursor()
    c.execute("SELECT rowid, pitch_mean FROM words WHERE pitch_mean > 0")
    rows = c.fetchall()
    if len(rows) < 2:
        print("⚠️ Not enough words with pitch; using UNKNOWN.")
        return
    pitches = np.array([r[1] for r in rows])
    median_pitch = np.median(pitches)
    print(f"📊 Median pitch: {median_pitch:.1f} Hz")
    for rowid, pitch in rows:
        speaker = "SPEAKER_0" if pitch >= median_pitch else "SPEAKER_1"
        c.execute("UPDATE words SET speaker = ? WHERE rowid = ?", (speaker, rowid))
    print(f"✅ Assigned speakers to {len(rows)} words.")

def compute_utterance_features(conn):
    c = conn.cursor()
    c.execute("SELECT uuid, start_ms, end_ms, text FROM utterances")
    utterances = c.fetchall()
    for uid, start, end, text in utterances:
        c.execute("SELECT word_text, pitch_mean, energy_mean, spectral_centroid, zcr, speaker FROM words WHERE utterance_uuid = ?", (uid,))
        words = c.fetchall()
        if not words:
            continue
        # Convert energy from bytes to float if necessary
        speaker_counts = {}
        pitch_vals = []
        energy_vals = []
        centroid_vals = []
        zcr_vals = []
        for w in words:
            speaker = w[5]
            if speaker != 'UNKNOWN':
                speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
            pitch = w[1]
            energy = w[2]
            if isinstance(energy, bytes):
                energy = float.fromhex(energy.hex()) if len(energy) == 4 else 0.0
            if pitch > 0:
                pitch_vals.append(pitch)
            if energy > 0:
                energy_vals.append(energy)
            centroid = w[3]
            if centroid > 0:
                centroid_vals.append(centroid)
            zcr = w[4]
            if zcr > 0:
                zcr_vals.append(zcr)

        pitch_mean = np.mean(pitch_vals) if pitch_vals else 0
        pitch_std = np.std(pitch_vals) if pitch_vals else 0
        energy_mean = np.mean(energy_vals) if energy_vals else 0
        energy_std = np.std(energy_vals) if energy_vals else 0
        centroid_mean = np.mean(centroid_vals) if centroid_vals else 0
        zcr_mean = np.mean(zcr_vals) if zcr_vals else 0

        # Text features
        sentiment = analyzer.polarity_scores(text)['compound']
        keywords = get_keywords(text)
        proper_nouns = count_proper_nouns(text)
        has_num = has_numbers(text)
        speaking_rate = len(text.split()) / ((end - start) / 1000.0) if (end - start) > 0 else 0

        # Vagueness (higher = more vague)
        vagueness = 1.0
        if len(speaker_counts) < 2:
            vagueness += 0.2
        if pitch_std < 10:
            vagueness += 0.2
        if energy_std < 0.05:
            vagueness += 0.2
        if abs(sentiment) < 0.2:
            vagueness += 0.3
        if len(text.split()) < 5:
            vagueness += 0.3
        if len(json.loads(keywords)) <= 1:
            vagueness += 0.3
        if proper_nouns >= 2:
            vagueness -= 0.3
        if has_num:
            vagueness -= 0.3
        vagueness = max(0.0, min(2.0, vagueness))

        # Layer
        if vagueness >= 1.2:
            layer = 1
        elif vagueness >= 0.6:
            layer = 2
        else:
            layer = 3

        # Update utterance
        c.execute("""UPDATE utterances SET
            pitch_mean=?, pitch_std=?, energy_mean=?, energy_std=?,
            spectral_centroid=?, zcr=?, sentiment=?, keywords=?,
            proper_nouns=?, has_numbers=?, speaking_rate=?,
            vagueness=?, layer=?, feature_version=?
            WHERE uuid=?""",
            (pitch_mean, pitch_std, energy_mean, energy_std,
             centroid_mean, zcr_mean, sentiment, keywords,
             proper_nouns, has_num, speaking_rate,
             vagueness, layer, 2, uid))
    print(f"✅ Updated {len(utterances)} utterances with features and layers.")

def main():
    conn = sqlite3.connect(DB)
    print("👥 Assigning speakers...")
    assign_speakers(conn)
    print("📊 Computing utterance features and layers...")
    compute_utterance_features(conn)
    conn.commit()
    conn.close()
    print("✅ Done.")

if __name__ == '__main__':
    main()
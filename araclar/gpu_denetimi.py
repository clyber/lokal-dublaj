"""Ekran kartı denemesi: yazıya dökme modeli CUDA'da açılıp kısa bir sesi döker, EMA bir Türkçe cümle seslendirir.
İlk çalıştırmada modeller indirilir (~1,6 GB + 34 MB). Çalıştır: python araclar/gpu_denetimi.py"""
import sys, time, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ortak

A = ortak.ayar()
ortak.cuda_dll_yolu()
import numpy as np
from faster_whisper import WhisperModel

t = time.time()
m = WhisperModel(A["yaziya_dokme"]["model"], device="cuda", compute_type="float16")
print(f"tamam: yazıya dökme modeli ekran kartında açıldı ({time.time() - t:.1f} sn)")
wavs = sorted(A["calisma_klasoru"].glob("*/ses16k.wav"))
if wavs:  # elde gerçek bir konuşma sesi varsa ilk 20 sn'sini dök
    with wave.open(str(wavs[0])) as wf:
        ses = np.frombuffer(wf.readframes(16000 * 20), dtype=np.int16).astype(np.float32) / 32768
else:  # yoksa 3 sn sessizlik: yalnız hattın çalıştığı sınanır
    ses = np.zeros(16000 * 3, dtype=np.float32)
    print("atlandı: gerçek konuşmanın tanınması (elde ses16k.wav yok; sessizlikle yalnız hat sınandı)")
segs, info = m.transcribe(ses, beam_size=5)
metin = " ".join(s.text.strip() for s in segs)
print(f"tamam: yazıya döküm çalıştı (dil {info.language}): {metin[:100] or '(sessizlik)'}")

from ema_lightning import EMA
t = time.time()
s = EMA().say(["Vidayı sıfır virgül sekiz newton metreye sıkın."])[0]
assert len(s.audio) / s.sample_rate > 0.5, "EMA ses üretmedi"
print(f"tamam: Türkçe ses üretildi ({len(s.audio) / s.sample_rate:.1f} sn ses, {time.time() - t:.1f} sn)")

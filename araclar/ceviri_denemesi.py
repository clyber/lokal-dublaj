"""Gerçek çeviri denemesi: ayardaki çeviri sunucusu + seçili modelle 3 cümle (ortak.deneme_cevirisi). kur.ps1 -Dogrula çağırır.
Çıkış: 0 geçti, 1 model cevap verdi ama denemeyi geçemedi (hata), 2 KULLANICI ADIMI BEKLİYOR (LM Studio kapalı, model
seçilmemiş ya da sunucuda yok). Çalıştır: python araclar/ceviri_denemesi.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ortak

c = ortak.ayar()["ceviri"]
try:
    var = [k for k, _ in ortak.model_listesi(c["adres"])]
except ortak.Hata as e:
    print(f"KULLANICI ADIMI BEKLİYOR: {e}")
    sys.exit(2)
model = c["model"] or (var[0] if len(var) == 1 else "")  # cevir.py ile aynı kural: seçim yoksa tek model
if not model:
    print("KULLANICI ADIMI BEKLİYOR: çeviri modeli seçilmedi — saatin yanındaki Lokal Dublaj simgesi → Çeviri modeli"
          + ("" if var else " (önce LM Studio'da bir sohbet modeli indir)"))
    sys.exit(2)
if model not in var:
    print(f"KULLANICI ADIMI BEKLİYOR: seçili model ({model}) çeviri sunucusunda yok — LM Studio'da yükle ya da simgeden başka model seç")
    sys.exit(2)
try:
    tr = ortak.deneme_cevirisi(c["adres"], model)
except Exception as e:
    print(f"HATA: {model} deneme çevirisini geçemedi: {e}")
    sys.exit(1)
print(f"tamam: {model} ile deneme çevirisi geçti:", " / ".join(tr.values()))

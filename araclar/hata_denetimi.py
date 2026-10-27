"""Hata yolunun öz denetimi: çeviri sunucusu kapalıyken açık mesaj; bilinmeyen bağlantı reddi. python araclar/hata_denetimi.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.argv = ["cevir.py", "x"]
import cevir, ortak

cevir.A["ceviri"]["adres"] = "http://127.0.0.1:9/v1"  # kimsenin dinlemediği port
try:
    cevir.ceviri_modeli()
    raise AssertionError("kapalı sunucu fark edilmedi")
except cevir.Hata as e:
    assert "Çeviri sunucusu kapalı" in str(e), e
    print("tamam: kapalı çeviri sunucusu ->", e)
try:
    ortak.video_id("https://vimeo.com/123")
    raise AssertionError("YouTube olmayan bağlantı kabul edildi")
except ValueError:
    print("tamam: YouTube olmayan bağlantı reddedildi")

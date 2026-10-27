"""Hata yolunun öz denetimi: çeviri sunucusu kapalıyken açık mesaj; bilinmeyen bağlantı reddi. python araclar/hata_denetimi.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.argv = ["cevir.py", "x"]
import tempfile
import cevir, ortak

cevir.A["ceviri"]["adres"] = "http://127.0.0.1:9/v1"  # kimsenin dinlemediği port
try:
    cevir.ceviri_modeli(Path(tempfile.mkdtemp()))
    raise AssertionError("kapalı sunucu fark edilmedi")
except cevir.Hata as e:
    assert "Çeviri sunucusu kapalı" in str(e), e
    print("tamam: kapalı çeviri sunucusu ->", e)
try:
    ortak.video_id("https://vimeo.com/123")
    raise AssertionError("YouTube olmayan bağlantı kabul edildi")
except ValueError:
    print("tamam: YouTube olmayan bağlantı reddedildi")

# boş kalmış belirteç dosyası (üreten süreç yazamadan öldü): hata yerine güvenle yeniden üretilmeli
asil_kok, gecici = ortak.KOK, Path(tempfile.mkdtemp())
try:
    ortak.KOK = gecici
    (gecici / ".belirtec").write_text("")
    b = ortak.belirtec()
    assert len(b) >= 32 and (gecici / ".belirtec").read_text().strip() == b, "boş belirteç yeniden üretilmedi"
    assert ortak.belirtec() == b, "belirteç ikinci çağrıda değişti"
    print("tamam: boş belirteç dosyası yeniden üretildi")
finally:
    ortak.KOK = asil_kok
    import shutil; shutil.rmtree(gecici, ignore_errors=True)

# R6-03: -Dogrula'nın gerçek çeviri denemesi: kapalı sunucu / seçimsiz / olmayan model = 2 (kullanıcı adımı), bozuk = 1
import contextlib, io, runpy
asil =ortak.ayar, ortak.model_listesi, ortak.ceviri_sor
def dene(adres, model, liste=None, cevap="0\t12 volt\n1\t0,8 Nm\n2\tfan"):
    ortak.ayar = lambda: {"ceviri": {"adres": adres, "model": model}}
    ortak.model_listesi = asil[1] if liste is None else (lambda a: [(k, None) for k in liste])
    ortak.ceviri_sor = lambda a, m, i: cevap
    try:  # betiğin kasıtlı HATA/KULLANICI ADIMI satırları -Dogrula çıktısında gerçek sonuç sanılmasın
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(Path(__file__).parent / "ceviri_denemesi.py"), run_name="__main__")
        return 0
    except SystemExit as e:
        return e.code
try:
    assert dene("http://127.0.0.1:9/v1", "m") == 2, "kapalı çeviri sunucusu kullanıcı adımı sayılmadı"
    assert dene("x", "", ["a", "b"]) == 2, "seçimsiz model kullanıcı adımı sayılmadı"
    assert dene("x", "yok", ["a"]) == 2, "sunucuda olmayan model kullanıcı adımı sayılmadı"
    assert dene("x", "a", ["a"], "anlamsız cevap") == 1, "denemeyi geçemeyen model başarı sayıldı"
    assert dene("x", "a", ["a"]) == 0
finally:
    ortak.ayar, ortak.model_listesi, ortak.ceviri_sor = asil
print("tamam: gerçek çeviri denemesi kapalı/seçimsiz/olmayan modelde 'kullanıcı adımı' (2), bozuk cevapta hata (1)")

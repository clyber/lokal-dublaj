"""Çeviri modeli seçiminin öz denetimi: ayara kayıt, yarım işin başladığı modelle sürmesi, seçimsiz durum, deneme
çevirisinin denetimleri. Çeviri sunucusu ve ekran kartı gerekmez. Çalıştır: python araclar/model_denetimi.py"""
import json, shutil, sys, tempfile, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.argv = ["cevir.py", "x"]
import cevir, ortak

gecici = Path(tempfile.mkdtemp())
asil_kok = ortak.KOK
try:
    # model_kaydet: yalnız [ceviri] model satırı değişir, yorumlar ve öteki bölümler kalır; dosya yoksa örnekten
    shutil.copy(asil_kok / "ayarlar.ornek.toml", gecici / "ayarlar.ornek.toml")
    ortak.KOK = gecici
    ortak.model_kaydet("gemma-4-12b-it")
    m = (gecici / "ayarlar.toml").read_text("utf-8")
    t = tomllib.loads(m)
    assert t["ceviri"]["model"] == "gemma-4-12b-it" and t["yaziya_dokme"]["model"].startswith("mobiuslabs"), t
    assert "# öneri: yaz" in m and m.count("model = ") == 2, "yorum ya da öteki model satırı bozuldu"
    ortak.model_kaydet('qwen"3.5')  # tırnaklı ad da güvenle yazılmalı
    assert tomllib.loads((gecici / "ayarlar.toml").read_text("utf-8"))["ceviri"]["model"] == 'qwen"3.5'
    (gecici / "ayarlar.toml").write_text('hedef_dil = "tr"\n[ceviri]\nadres = "x"\n[ses]\nmotor = "ema"\n', "utf-8")
    ortak.model_kaydet("m1")  # model satırı hiç yoksa bölüme eklenir
    t = tomllib.loads((gecici / "ayarlar.toml").read_text("utf-8"))
    assert t["ceviri"] == {"model": "m1", "adres": "x"} and t["ses"]["motor"] == "ema", t
    print("tamam: model ayar dosyasına yazılıyor, geri kalan korunuyor")
    ortak.KOK = asil_kok

    # ceviri_modeli: sunucu listesi taklit edilir
    liste = [("gemma-4-12b-it", False), ("qwen3.5-9b", True)]
    ortak.model_listesi = lambda adres: liste
    d = gecici / "vid"; d.mkdir()
    cevir.A["ceviri"]["model"] = ""
    try:
        cevir.ceviri_modeli(d)
        raise AssertionError("iki model varken sessizce biri seçildi")
    except cevir.Hata as e:
        assert "seçilmedi" in str(e), e
    print("tamam: seçim yokken ve birden çok model varken kullanıcıdan seçmesi isteniyor")

    liste = [("gemma-4-12b-it", False)]
    assert cevir.ceviri_modeli(d) == "gemma-4-12b-it"  # tek model: o
    liste = [("gemma-4-12b-it", False), ("qwen3.5-9b", True)]
    cevir.A["ceviri"]["model"] = "gemma-4-12b-it"
    assert cevir.ceviri_modeli(d) == "gemma-4-12b-it"
    assert json.loads((d / "uretim.json").read_text("utf-8"))["model"] == "gemma-4-12b-it"
    print("tamam: kullanılan model video klasörüne kaydediliyor")

    # yarım iş: ayar değişse de başladığı modelle sürer (M01: iki modelin çevirisi karışmasın)
    (d / "ceviri.json").write_text('{"0": "a"}', "utf-8")
    cevir.A["ceviri"]["model"] = "qwen3.5-9b"
    assert cevir.ceviri_modeli(d) == "gemma-4-12b-it", "yarım iş yeni modelle devam etti"
    liste = [("qwen3.5-9b", True)]
    try:
        cevir.ceviri_modeli(d)
        raise AssertionError("yarım işin modeli yokken başka modelle devam edildi")
    except cevir.Hata as e:
        assert "yarıda kalmıştı" in str(e), e
    print("tamam: yarım iş başladığı modelle sürüyor, o model yoksa açık hata")

    # kaydı olmayan eski iş: model uydurulmaz
    d2 = gecici / "eski"; d2.mkdir(); (d2 / "ceviri.json").write_text("{}", "utf-8")
    cevir.ceviri_modeli(d2)
    assert not (d2 / "uretim.json").exists(), "eski işe model kaydı uyduruldu"
    # ayardaki model sunucuda yoksa
    cevir.A["ceviri"]["model"] = "olmayan"
    try:
        cevir.ceviri_modeli(gecici / "vid3")
        raise AssertionError("sunucuda olmayan model kabul edildi")
    except cevir.Hata as e:
        assert "sunucuda yok" in str(e), e
    print("tamam: eski işe kayıt uydurulmuyor; sunucuda olmayan model reddediliyor")

    # deneme çevirisi: biçim ve sayı denetimi
    ortak.ceviri_sor = lambda a, m, i: "0\t12 volt'u aşmayın.\n1\tVidayı 0,8 newton metreye sıkın.\n2\tMotor durduktan sonra fan çalışmaya devam eder."
    assert len(ortak.deneme_cevirisi("x", "m")) == 3
    ortak.ceviri_sor = lambda a, m, i: "0\tOn iki volt'u aşmayın.\n1\tVidayı 0,8 Nm sıkın.\n2\tFan çalışır."
    try:
        ortak.deneme_cevirisi("x", "m")
        raise AssertionError("sayısı bozulan çeviri geçti")
    except ortak.Hata as e:
        assert "sayıları" in str(e), e
    ortak.ceviri_sor = lambda a, m, i: "İşte çeviriler: 12 volt..."
    try:
        ortak.deneme_cevirisi("x", "m")
        raise AssertionError("biçime uymayan cevap geçti")
    except ortak.Hata as e:
        assert "biçimde" in str(e), e
    print("tamam: deneme çevirisi biçimi ve sayıları denetliyor")
finally:
    ortak.KOK = asil_kok
    shutil.rmtree(gecici, ignore_errors=True)

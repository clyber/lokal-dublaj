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

    # R6-06: geçerli her TOML biçiminde; kaçışlı addan sonra normal ada geçiş, tek tırnak, girinti, yorum, bölümsüz dosya
    def kaydet_oku(once, *modeller):
        if once is not None:
            (gecici / "ayarlar.toml").write_text(once, "utf-8")
        for m in modeller:
            ortak.model_kaydet(m)
        metin = (gecici / "ayarlar.toml").read_text("utf-8")
        return metin, tomllib.loads(metin)
    m, t = kaydet_oku('[ceviri]\nmodel = "a"\n', 'qwen"3.5', "gemma")
    assert t["ceviri"]["model"] == "gemma", m
    m, t = kaydet_oku("[ceviri]\nmodel = 'gemma' # tek tırnak\nadres = 'x'\n", "qwen3.5-9b")
    assert t["ceviri"] == {"model": "qwen3.5-9b", "adres": "x"} and "# tek tırnak" in m, m
    m, t = kaydet_oku('[ceviri]\n  model = "a\\\\b"   # girintili\n[ses]\nmodel = "dokunma"\n', "yeni")
    assert t["ceviri"]["model"] == "yeni" and t["ses"]["model"] == "dokunma" and "# girintili" in m, m
    m, t = kaydet_oku('hedef_dil = "tr"\n', "m2")
    assert t == {"hedef_dil": "tr", "ceviri": {"model": "m2"}}, m
    m, t = kaydet_oku("[ceviri]", "m3")  # son satırda başlık, satır sonu yok
    assert t["ceviri"]["model"] == "m3", m
    m, t = kaydet_oku('[ceviri]\r\nmodel = "a"\r\n', "çeviri-modeli")  # CRLF, ASCII dışı ad
    assert t["ceviri"]["model"] == "çeviri-modeli", m
    print("tamam R6-06: model kaydı tırnaklı/tek tırnaklı/girintili/bölümsüz dosyada geçerli TOML üretiyor")
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

    # kaydı olmayan eski iş, çevirisi tamam: model uydurulmaz, devam eder (yalnız seslendirme kalmış)
    parcalar = json.dumps([{"id": 0, "bas": 0, "son": 1, "metin": "a"}, {"id": 1, "bas": 1, "son": 2, "metin": "b"}])
    d2 = gecici / "eski"; d2.mkdir(); (d2 / "ceviri.json").write_text('{"0": "x", "1": "y"}', "utf-8")
    (d2 / "parcalar.json").write_text(parcalar, "utf-8")
    cevir.ceviri_modeli(d2)
    assert not (d2 / "uretim.json").exists(), "eski işe model kaydı uyduruldu"

    # R6-01: kaydı olmayan eski iş, çevirisi EKSİK: sessizce yeni modelle tamamlanmaz, kurtarma yolu söylenir
    d4 = gecici / "eski-yarim"; d4.mkdir(); (d4 / "ceviri.json").write_text('{"0": "x"}', "utf-8")
    (d4 / "parcalar.json").write_text(parcalar, "utf-8")
    try:
        cevir.ceviri_modeli(d4)
        raise AssertionError("R6-01: modeli bilinmeyen yarım çeviri yeni modelle sürdürüldü")
    except cevir.Hata as e:
        assert "bilinmiyor" in str(e) and "baştan" in str(e) and getattr(e, "yeniden_cevir", False), e
    # kayıtlı yarım iş, çeviri adresi değişmiş: aynı ad başka sunucuda başka model olabilir
    d5 = gecici / "adres"; d5.mkdir(); (d5 / "ceviri.json").write_text('{"0": "x"}', "utf-8")
    (d5 / "parcalar.json").write_text(parcalar, "utf-8")
    (d5 / "uretim.json").write_text(json.dumps({"model": "qwen3.5-9b", "adres": "http://baska:1234/v1"}), "utf-8")
    try:
        cevir.ceviri_modeli(d5)
        raise AssertionError("R6-01: başka adreste başlamış yarım iş sessizce sürdü")
    except cevir.Hata as e:
        assert "adres" in str(e) and getattr(e, "yeniden_cevir", False), e
    (d5 / "uretim.json").write_text(json.dumps({"model": "qwen3.5-9b", "adres": cevir.A["ceviri"]["adres"] + "/"}), "utf-8")
    assert cevir.ceviri_modeli(d5) == "qwen3.5-9b", "aynı adres + model ile yarım iş sürmedi"
    # yeni kayıt adresi de içerir
    assert json.loads((d / "uretim.json").read_text("utf-8")).get("adres"), "uretim.json'da çeviri adresi yok"
    print("tamam R6-01: kökeni bilinmeyen / adresi değişen yarım çeviri açık hata veriyor, kayıt adres+model")

    # --yeniden-cevir: yalnız çeviri ve ondan türeyen ses silinir, yazıya döküm kalır; hazır videoya dokunulmaz
    d6 = gecici / "yeniden"; (d6 / "tts-ema").mkdir(parents=True)
    for f in ("parcalar.json", "ses16k.wav", "ceviri.json", "uretim.json", "turkce-ema.wav", "tts-ema/0.wav", "hata.txt"):
        (d6 / f).write_text("x", "utf-8")
    assert cevir.ceviriyi_sil(d6) is True
    kalan = sorted(str(p.relative_to(d6)) for p in d6.rglob("*"))
    assert kalan == ["hata.txt", "parcalar.json", "ses16k.wav"], kalan
    (d6 / "ceviri.json").write_text("x", "utf-8"); (d6 / "bitti-ema").write_text("x", "utf-8")
    assert cevir.ceviriyi_sil(d6) is False and (d6 / "ceviri.json").exists(), "hazır videonun çevirisi silindi"
    print("tamam: --yeniden-cevir yazıya dökümü koruyor, hazır videoya dokunmuyor")
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

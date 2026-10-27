"""Güvenilirlik öz denetimi: eksik çeviri, bayat yarım indirme, ölen iş. Ekran kartı ve internet gerekmez.
Çalıştır: python araclar/guvenilirlik_denetimi.py   — her satır "tamam" ya da hata.
"""
import json, os, shutil, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.argv = ["cevir.py", "x"]
import cevir, ortak, sunucu

gecici = Path(tempfile.mkdtemp())
try:
    # K01: çevirinin bir kısmı hiç gelmezse iş "hazır" sayılmamalı (eskiden yarıdan azı eksikse geçiyordu)
    p = [{"id": i, "bas": i, "son": i + 1, "metin": f"cumle {i}"} for i in range(10)]
    ortak.ceviri_sor = lambda adres, model, istem: "\n".join(f"{i}\tçeviri {i}" for i in range(6))  # 4 parça hep eksik
    d1 = gecici / "k01"; d1.mkdir()
    try:
        cevir.cevir(p, d1, "model")
        raise AssertionError("K01: 4/10 eksik çeviri başarı sayıldı")
    except cevir.Hata as e:
        assert "4" in str(e), e
        print("tamam K01: eksik çeviri hata veriyor ->", e)

    # Bağlam penceresi dolunca grup ikiye bölünerek yine tamamlanmalı (10-26'da gerçek videoda yakalandı)
    def dar_pencere(adres, model, istem):
        ids = [int(s.split("\t")[0]) for s in istem.split("id\tsüre\tmetin\n")[1].splitlines()]
        if len(ids) > 3:
            raise cevir.Hata('Çeviri sunucusu isteği reddetti (400): {"message":"Context size has been exceeded."}')
        return "\n".join(f"{i}\tçeviri {i}" for i in ids)
    ortak.ceviri_sor = dar_pencere
    d1b = gecici / "k01b"; d1b.mkdir()
    sonuc = cevir.cevir(p, d1b, "model")
    assert len(sonuc) == 10, f"bölme sonrası eksik: {len(sonuc)}"
    print("tamam: bağlam penceresi dolunca grup bölünüp tamamlandı")

    # K02: sahibi ölmüş, uzun süredir büyümeyen .part dosyası beklemeyi sonsuz yapmamalı
    d2 = gecici / "k02"; d2.mkdir()
    part = d2 / "ses.m4a.part"; part.write_bytes(b"x")
    eski = time.time() - 600
    os.utime(part, (eski, eski))
    assert cevir.indirme_bekle(d2, d2 / "ses.m4a", bayat_sn=120, aralik=0.01) is False, "K02: bayat indirme beklenmeye devam etti"
    assert not part.exists(), "K02: bayat .part silinmedi"
    print("tamam K02: bayat yarım indirme temizlendi, beklenmedi")

    # K03: işi yapan süreç yokken ara dosyalar duruyorsa "hazırlanıyor"da takılı kalmamalı -> "yarim"
    sunucu.IS = gecici
    d3 = gecici / "ABCDEFGHIJK"; d3.mkdir()
    (d3 / "parcalar.json").write_text(json.dumps(p), "utf-8")
    (d3 / "ceviri.json").write_text(json.dumps({"0": "a"}), "utf-8")
    dr = sunucu.durum("ABCDEFGHIJK")
    assert dr["durum"] == "yarim", f"K03: süreç yokken durum {dr}"
    # aynı klasörde canlı bir süreç video kilidini tutuyorsa yine "hazırlanıyor"
    with open(d3 / ".is-kilit", "a+") as f:
        assert ortak.kilit_dene(f)
        import subprocess
        r = subprocess.run([sys.executable, "-c",
                            f"import sys; sys.path.insert(0, r'{Path(__file__).resolve().parent.parent}'); "
                            f"import sunucu; from pathlib import Path; sunucu.IS = Path(r'{gecici}'); print(sunucu.durum('ABCDEFGHIJK')['durum'])"],
                           capture_output=True, text=True)
        assert r.stdout.strip() == "hazirlaniyor", f"K03: kilit tutulurken durum {r.stdout!r} {r.stderr[-300:]}"
        ortak.kilit_birak(f)
    print("tamam K03: süreç ölünce 'yarim', yaşarken 'hazirlaniyor'")
finally:
    shutil.rmtree(gecici, ignore_errors=True)

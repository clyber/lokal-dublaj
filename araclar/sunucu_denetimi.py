"""Sunucunun izole öz denetimi: Range (G03), süre girdisi, bozuk belirteç/bilet (R6-04), beklenmeyen hata, bozuk
uretim.json (R6-07), aynı video için tek süreç (K06), eşzamanlı iş sınırı (G02), baştan çevirme seçeneği (R6-01).
Geçici iş klasörü ve boş bir port kullanır; gerçek is/ ve 8799'daki sunucuya dokunmaz, cevir.py başlatmaz (taklit).
Çalıştır: python araclar/sunucu_denetimi.py   — her satır "tamam" ya da sonda başarısızların listesi."""
import http.client, json, shutil, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ortak, sunucu

gecici = Path(tempfile.mkdtemp())
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
sunucu.IS, sunucu.PORT = gecici, PORT
baslatilan = []  # taklit Popen'e gelen komut satırları


class SahteSurec:  # cevir.py yerine: yavaş açılır (yarış penceresi), hep yaşıyor görünür
    def __init__(self, komut, **_):
        time.sleep(0.3)
        baslatilan.append(komut)

    def poll(self):
        return None


asil_popen = subprocess.Popen
subprocess.Popen = SahteSurec
srv = sunucu.ThreadingHTTPServer(("127.0.0.1", PORT), sunucu.Isleyici)
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = {"X-TR-Belirtec": ortak.belirtec()}
basarisiz = []


def istek(yol, yontem="GET", baslik=None):
    """(durum, başlıklar, gövde); sunucu bağlantıyı cevapsız koparırsa (durum None, {}, hata adı)."""
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
    try:
        c.putrequest(yontem, yol)
        for k, v in (baslik or {}).items():
            c.putheader(k, v)
        c.endheaders()
        r = c.getresponse()
        return r.status, dict(r.getheaders()), r.read()
    except Exception as e:
        return None, {}, type(e).__name__.encode()
    finally:
        c.close()


def kontrol(ad, kosul, ayrinti=""):
    if kosul:
        print("tamam:", ad)
    else:
        basarisiz.append(f"{ad} {ayrinti}")
        print("BAŞARISIZ:", ad, ayrinti)


try:
    # G03: 100 baytlık hazır ses + boş dosyalı hazır ses
    for vid, veri in (("AAAAAAAAAAA", bytes(range(100))), ("BBBBBBBBBBB", b"")):
        (gecici / vid).mkdir()
        (gecici / vid / "turkce-ema.m4a").write_bytes(veri)
        (gecici / vid / "bitti-ema").write_text("x", "utf-8")
    ses = lambda vid, rng=None: istek(f"/ses/{vid}.m4a?b={ortak.ses_bileti(vid)}", baslik={"Range": rng} if rng else None)
    k, h, g = ses("AAAAAAAAAAA")
    kontrol("Range yok -> 200 tüm dosya", k == 200 and g == bytes(range(100)), (k, len(g)))
    for rng, bas, son in (("bytes=0-99", 0, 99), ("bytes=0-999", 0, 99), ("bytes=10-19", 10, 19), ("bytes=-10", 90, 99),
                          ("bytes=95-", 95, 99)):
        k, h, g = ses("AAAAAAAAAAA", rng)
        kontrol(f"{rng} -> 206 {bas}-{son}", k == 206 and h.get("Content-Range") == f"bytes {bas}-{son}/100"
                and g == bytes(range(bas, son + 1)) and h.get("Content-Length") == str(son - bas + 1), (k, h.get("Content-Range"), len(g)))
    for rng in ("bytes=200-", "bytes=100-", "bytes=90-20", "bytes=-0", "bytes=0-1,5-6", "bytes=abc", "items=0-5"):
        k, h, g = ses("AAAAAAAAAAA", rng)
        kontrol(f"{rng} -> 416", k == 416 and h.get("Content-Range") == "bytes */100", (k, h.get("Content-Range")))
    k, h, g = ses("BBBBBBBBBBB", "bytes=0-")
    kontrol("boş dosya + Range -> 416 bytes */0", k == 416 and h.get("Content-Range") == "bytes */0", (k, h.get("Content-Range")))
    k, h, g = ses("BBBBBBBBBBB")
    kontrol("boş dosya Range yok -> 200 boş", k == 200 and g == b"", (k, g))
    buyuk = bytes(range(256)) * 1000  # 256 KB: parça parça yazım
    (gecici / "AAAAAAAAAAA" / "turkce-ema.m4a").write_bytes(buyuk)
    k, h, g = ses("AAAAAAAAAAA", "bytes=1000-")
    kontrol("256 KB dosya, bytes=1000- -> 206 doğru veri", k == 206 and g == buyuk[1000:], (k, len(g)))

    # süre girdisi: sonlu, negatif olmayan, makul
    for sure in ("NaN", "Infinity", "-inf", "-5", "abc", "1e9"):
        k, h, g = istek(f"/bilgi/AAAAAAAAAAA?sure={sure}", baslik=B)
        kontrol(f"sure={sure} -> 400", k == 400, (k, g[:80]))
    k, h, g = istek("/bilgi/AAAAAAAAAAA?sure=600", baslik=B)
    kontrol("sure=600 -> 200 + tahmin", k == 200 and "tahmin_dk" in json.loads(g), (k, g[:80]))

    # R6-04: ASCII dışı / boş belirteç ve bilet bağlantıyı koparmamalı, 401 dönmeli
    k, h, g = istek("/ses/AAAAAAAAAAA.m4a?b=%C3%A9")
    kontrol("ASCII dışı bilet -> 401", k == 401, (k, g))
    k, h, g = istek("/durum/AAAAAAAAAAA", baslik={"X-TR-Belirtec": "é".encode("utf-8")})
    kontrol("ASCII dışı belirteç -> 401", k == 401, (k, g))
    k, h, g = istek("/durum/AAAAAAAAAAA", baslik={"X-TR-Belirtec": ""})
    kontrol("boş belirteç -> 401", k == 401, (k, g))

    # beklenmeyen istisna: bağlantı kopmasın, JSON 500
    asil, asil_iz = sunucu.hiz_katsayisi, sunucu.traceback.print_exc
    sunucu.hiz_katsayisi = lambda: 1 / 0
    sunucu.traceback.print_exc = lambda *a, **k: None  # kasıtlı hatanın izi çıktıyı kirletmesin
    k, h, g = istek("/bilgi/AAAAAAAAAAA?sure=60", baslik=B)
    sunucu.hiz_katsayisi, sunucu.traceback.print_exc = asil, asil_iz
    kontrol("beklenmeyen istisna -> 500 JSON", k == 500 and "hata" in json.loads(g or b"{}"), (k, g[:80]))

    # R6-07: yarım/bozuk uretim.json ve parcalar.json okunurken sunucu çökmesin
    d = gecici / "CCCCCCCCCCC"; d.mkdir()
    (d / "uretim.json").write_text('{"model": "ya', "utf-8")
    (d / "parcalar.json").write_text('[{"id": 0', "utf-8")
    k, h, g = istek("/bilgi/CCCCCCCCCCC", baslik=B)
    kontrol("bozuk uretim.json/parcalar.json -> 200, model yok", k == 200 and json.loads(g).get("model") is None, (k, g[:80]))

    # K06: aynı video için eşzamanlı iki istek tek süreç açmalı
    sonuc = []
    t = [threading.Thread(target=lambda: sonuc.append(istek("/hazirla/DDDDDDDDDDD", "POST", B))) for _ in range(2)]
    [x.start() for x in t]; [x.join() for x in t]
    n = sum("DDDDDDDDDDD" in c for c in baslatilan)
    kontrol("aynı video, eşzamanlı iki istek -> tek süreç", n == 1, f"{n} süreç")

    # G02: sunucunun açtığı canlı iş sayısı sınırlı, aşınca açık JSON cevabı
    sunucu.surecler.clear()
    cevaplar = [istek(f"/hazirla/E{i}EEEEEEEEE", "POST", B) for i in range(4)]
    dolu = [json.loads(c[2]) for c in cevaplar if c[0] == 429]
    kontrol("4. eşzamanlı iş reddedildi (429, durum dolu)", len(dolu) == 1 and dolu[0].get("durum") == "dolu",
            [c[0] for c in cevaplar])

    # R6-01: ?cevir=yeniden -> cevir.py --yeniden-cevir; hazır videoya dokunulmaz; köken hatası durumda işaretli
    sunucu.surecler.clear()
    d = gecici / "FFFFFFFFFFF"; d.mkdir()
    (d / "hata.txt").write_text("Önceki çevirinin modeli bilinmiyor", "utf-8")
    (d / "koken-hatasi").touch()
    k, h, g = istek("/durum/FFFFFFFFFFF", baslik=B)
    kontrol("köken hatası durumda yeniden_cevir ile", k == 200 and json.loads(g).get("yeniden_cevir") is True, (k, g[:120]))
    istek("/hazirla/FFFFFFFFFFF?cevir=yeniden", "POST", B)
    kontrol("?cevir=yeniden -> --yeniden-cevir", any("FFFFFFFFFFF" in c and "--yeniden-cevir" in c for c in baslatilan), baslatilan[-1:])
    kontrol("yeniden başlatınca köken işareti silindi", not (d / "koken-hatasi").exists())
    once = len(baslatilan)
    k, h, g = istek("/hazirla/AAAAAAAAAAA?cevir=yeniden", "POST", B)
    kontrol("hazır videoya ?cevir=yeniden süreç açmıyor", len(baslatilan) == once and json.loads(g).get("durum") == "hazir", (k, g[:80]))
finally:
    srv.shutdown()
    subprocess.Popen = asil_popen
    shutil.rmtree(gecici, ignore_errors=True)

assert not basarisiz, f"{len(basarisiz)} sunucu denetimi başarısız: {basarisiz}"
print("tamam: sunucu denetimi geçti")

"""Firefox eklentisinin konuştuğu yerel sunucu (yalnız bu bilgisayar: 127.0.0.1:<sunucu.port>, varsayılan 8799).

GET  /durum/<id>          -> {"durum": "hazir"|"hazirlaniyor"|"sirada"|"hata"|"turkce"|"yok", "ilerleme": "..."}
GET  /bilgi/<id>?sure=sn  -> durum + tahmini hazırlama süresi (ölçülmüş katsayı) + şu an ekran kartındaki video
GET  /ses/<id>.m4a        -> Türkçe ses (Range destekli: eklenti sarınca sesin ortasından ister)
POST /hazirla/<id>?ad=... -> cevir.py'yi öncelikli başlatır (yalnız X-TR-Ses başlığıyla: web sayfaları yollayamaz)
POST /kapat               -> sunucuyu kapatır (başlatıcı kullanır; aynı başlık şartı)
Çalıştır: baslatici.py (tepsi/pencere) ya da python sunucu.py   (ayarlar: ayarlar.toml)
"""
import json, re, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import ortak

A = ortak.ayar()
IS = A["calisma_klasoru"]
SES = A["ses"]["motor"]
MOTORLAR = ("ema", "chatterbox", "piper")
surecler = {}  # bu sunucunun başlattığı işler


def motor(vid):
    """Bu videonun sesi hangi motorla hazırlanmış / hazırlanıyor; yoksa ayardaki motor."""
    d = IS / vid
    for m in MOTORLAR:
        if (d / f"bitti-{m}").exists() or (d / f"tts-{m}").exists():
            return m
    return SES


def calisiyor(vid):
    """Bu video için yaşayan bir cevir.py var mı: bizim başlattığımız süreç ya da video kilidini tutan herhangi biri
    (toplu iş dahil). Kilit süreç ölünce kendiliğinden kalkar; dosyaların varlığı iş sürüyor demek değildir (K03)."""
    p = surecler.get(vid)
    if p is not None and p.poll() is None:
        return True
    f = IS / vid / ".is-kilit"
    if not f.exists():
        return False
    with open(f, "a+") as h:
        if ortak.kilit_dene(h):
            ortak.kilit_birak(h)
            return False
    return True


def durum(vid):
    d = IS / vid
    m = motor(vid)
    if (d / f"bitti-{m}").exists() and (d / f"turkce-{m}.m4a").exists():
        return {"durum": "hazir"}
    if (d / "zaten-turkce").exists():
        return {"durum": "turkce"}
    canli = calisiyor(vid)
    if (d / "hata.txt").exists() and not canli:
        return {"durum": "hata", "ilerleme": (d / "hata.txt").read_text("utf-8").strip()}
    if not d.exists() and not canli:
        return {"durum": "yok"}
    if not canli:
        # süreç yok: yarıda kalmış iş mi, önden indirilip sırasını bekleyen mi, şu an önden iniyor mu
        if any((d / f).exists() for f in ("parcalar.json", "ceviri.json", "ses16k.wav")):
            return {"durum": "yarim", "ilerleme": "Yarıda kalmış · devam etmek için bas (hazır kısımlar saklı)"}
        yarim = list(d.glob("*.part")) + list(d.glob("video.f*"))
        if yarim and time.time() - max(f.stat().st_mtime for f in yarim) < 120:
            return {"durum": "hazirlaniyor", "ilerleme": "Türkçe ses hazırlanıyor · 1/4 indiriliyor"}
        if (d / "ses.m4a").exists() or (d / "video.mp4").exists():
            return {"durum": "sirada", "ilerleme": "Sırada · önceki videolar bitince hazırlanacak"}
        return {"durum": "yok"}
    # düğmede okunacak metin: hangi aşamada, yüzde kaç (4 aşama: indir, yazıya dök, çevir, seslendir)
    parca = d / "parcalar.json"
    if parca.exists():
        n = len(json.loads(parca.read_text("utf-8")))
        cev = len(json.loads((d / "ceviri.json").read_text("utf-8"))) if (d / "ceviri.json").exists() else 0
        if cev < n:
            return {"durum": "hazirlaniyor", "ilerleme": f"Türkçe ses hazırlanıyor · 3/4 çeviri %{100 * cev // n}"}
        ts = len(list((d / f"tts-{m}").glob("*.wav"))) if (d / f"tts-{m}").exists() else 0
        if ts < n:
            return {"durum": "hazirlaniyor", "ilerleme": f"Türkçe ses hazırlanıyor · 4/4 seslendirme %{100 * ts // n}"}
        return {"durum": "hazirlaniyor", "ilerleme": "Türkçe ses hazırlanıyor · birleştiriliyor"}
    if (d / "ses16k.wav").exists():
        if calisan().get("vid") != vid:
            return {"durum": "hazirlaniyor", "ilerleme": "İndirildi · ekran kartı sırası bekleniyor"}
        return {"durum": "hazirlaniyor", "ilerleme": "Türkçe ses hazırlanıyor · 2/4 yazıya dökülüyor"}
    return {"durum": "hazirlaniyor", "ilerleme": "Türkçe ses hazırlanıyor · 1/4 indiriliyor"}


def calisan():
    """Şu an ekran kartında işlenen video (cevir.py kilidi alınca yazar); kilit boşsa kayıt bayattır."""
    try:
        c = json.loads((IS / ".calisan").read_text("utf-8"))
        with open(IS / ".gpu-kilit", "a+") as f:
            if ortak.kilit_dene(f):
                ortak.kilit_birak(f)
                return {}
        return c if not any((IS / c["vid"] / f"bitti-{m}").exists() for m in MOTORLAR) else {}
    except Exception:
        return {}


def hiz_katsayisi():
    """Ölçülmüş: hazırlama süresi / video süresi (toplu-durum.tsv'deki gerçek koşulardan, ortanca). Yoksa 1,5."""
    oranlar = []
    tsv = IS / "toplu-durum.tsv"
    for s in (tsv.read_text("utf-8").splitlines() if tsv.exists() else []):
        a = s.split("\t")
        if len(a) > 4 and a[2] == "tamam" and (dk := int(a[4].split()[0])) > 5:
            p = IS / a[1] / "parcalar.json"
            if p.exists():
                oranlar.append(dk / (json.loads(p.read_text("utf-8"))[-1]["son"] / 60))
    return sorted(oranlar)[len(oranlar) // 2] if oranlar else 1.5


def bilgi(vid, sure_sn):
    """Eklentinin bilgi paneli: bu video için ne durumda, ne kadar sürer, önünde ne var."""
    b = durum(vid)
    k = hiz_katsayisi()
    b["katsayi"] = round(k, 2)
    if sure_sn:
        b["tahmin_dk"] = round(2 + sure_sn / 60 * k)  # +2 dk: modellerin yüklenmesi, kısa videoda belirgin
    c = calisan()
    if c and c["vid"] != vid:
        b["gpu_mesgul"] = {"ad": c.get("ad", c["vid"]), "ilerleme": durum(c["vid"]).get("ilerleme", "")}
    return b


class Isleyici(BaseHTTPRequestHandler):
    def _json(self, veri, kod=200):
        b = json.dumps(veri, ensure_ascii=False).encode()
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if m := re.fullmatch(r"/durum/([\w-]{11})", u.path):
            return self._json(durum(m[1]))
        if m := re.fullmatch(r"/bilgi/([\w-]{11})", u.path):
            sure = float(parse_qs(u.query).get("sure", ["0"])[0] or 0)
            return self._json(bilgi(m[1], sure))
        if m := re.fullmatch(r"/ses/([\w-]{11})\.m4a", u.path):
            f = IS / m[1] / f"turkce-{motor(m[1])}.m4a"
            if not f.exists():
                return self._json({"hata": "ses yok"}, 404)
            boy = f.stat().st_size
            bas, son = 0, boy - 1
            if r := re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "")):
                bas = int(r[1]) if r[1] else max(0, boy - int(r[2]))
                son = int(r[2]) if r[1] and r[2] else boy - 1
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {bas}-{son}/{boy}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", "audio/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(son - bas + 1))
            self.end_headers()
            with f.open("rb") as h:
                h.seek(bas)
                self.wfile.write(h.read(son - bas + 1))
            return
        self._json({"hata": "bilinmeyen adres"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if self.headers.get("X-TR-Ses") != "1":  # yalnız eklenti: sıradan bir web sayfası bilgisayara iş yaptıramaz
            return self._json({"hata": "izin yok"}, 403)
        if m := re.fullmatch(r"/hazirla/([\w-]{11})", u.path):
            vid = m[1]
            if durum(vid)["durum"] in ("hazir", "hazirlaniyor", "turkce"):
                return self._json(durum(vid))
            (IS / vid / "hata.txt").unlink(missing_ok=True)  # hata sonrası yeniden deneme
            (IS / vid).mkdir(parents=True, exist_ok=True)
            ad = parse_qs(u.query).get("ad", [vid])[0]
            surecler[vid] = subprocess.Popen(
                [sys.executable, str(ortak.KOK / "cevir.py"), vid, "--ad", ad, "--oncelik"],
                stdout=open(IS / vid / "gunluk.txt", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
            return self._json({"durum": "hazirlaniyor", "ilerleme": "başlatıldı"})
        if u.path == "/kapat":  # başlatıcının "Durdur"u; süren cevir.py ayrı süreç, bitmeye devam eder
            self._json({"durum": "kapaniyor"})
            threading.Thread(target=self.server.shutdown).start()
            return
        self._json({"hata": "bilinmeyen adres"}, 404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    IS.mkdir(parents=True, exist_ok=True)
    port = A["sunucu"]["port"]
    print(f"Lokal Dublaj sunucusu: http://127.0.0.1:{port}  (iş klasörü {IS})", flush=True)
    ThreadingHTTPServer.allow_reuse_address = False  # Windows'ta port doluyken sessizce ikinci kez bağlanmasın
    ThreadingHTTPServer(("127.0.0.1", port), Isleyici).serve_forever()

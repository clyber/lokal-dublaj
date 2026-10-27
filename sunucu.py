"""Firefox eklentisinin konuştuğu yerel sunucu (yalnız bu bilgisayar: 127.0.0.1:<sunucu.port>, varsayılan 8799).

Her istek X-TR-Belirtec başlığında kurulum belirtecini ister (ortak.belirtec; eklenti köprüden alır), ses adresi
yalnız o videoya özel bilet (?b=...); Host 127.0.0.1/localhost değilse reddedilir. Yetkisiz istek: 401.
GET  /durum/<id>          -> {"durum": "hazir"|"hazirlaniyor"|"sirada"|"hata"|"turkce"|"yok", "ilerleme": "..."} (+ hazırsa "bilet")
GET  /bilgi/<id>?sure=sn  -> durum + tahmini hazırlama süresi (ölçülmüş katsayı) + şu an ekran kartındaki video + model
GET  /ses/<id>.m4a?b=...  -> Türkçe ses (tek aralıklı Range: eklenti sarınca sesin ortasından ister; karşılanamazsa 416)
POST /hazirla/<id>?ad=...[&cevir=yeniden] -> cevir.py'yi öncelikli başlatır (yeniden: çeviriyi baştan yapar);
                             aynı anda en çok AZAMI_IS iş, aşınca 429 {"durum": "dolu"}
POST /kapat               -> sunucuyu kapatır (başlatıcı kullanır)
Çalıştır: baslatici.py (tepsi/pencere) ya da python sunucu.py   (ayarlar: ayarlar.toml)
"""
import hmac, json, math, re, subprocess, sys, threading, time, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import ortak

A = ortak.ayar()
IS = A["calisma_klasoru"]
PORT = A["sunucu"]["port"]
BELIRTEC = ortak.belirtec()
SES = A["ses"]["motor"]
MOTORLAR = ("ema", "chatterbox", "piper")
AZAMI_IS = 3  # sunucunun aynı anda açık tuttuğu cevir.py (her biri indirir; ekran kartını zaten sırayla kullanırlar) (G02)
AZAMI_SURE = 86400  # sn; /bilgi?sure= üst sınırı
surecler = {}  # bu sunucunun başlattığı işler
baslatma_kilidi = threading.Lock()  # "çalışıyor mu" denetimi ile süreç açma tek hamle (K06)


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
    return ortak.kilitli(IS / vid / ".is-kilit")


def durum(vid):
    d = IS / vid
    m = motor(vid)
    if (d / f"bitti-{m}").exists() and (d / f"turkce-{m}.m4a").exists():
        return {"durum": "hazir"}
    if (d / "zaten-turkce").exists():
        return {"durum": "turkce"}
    canli = calisiyor(vid)
    if (d / "hata.txt").exists() and not canli:
        h = {"durum": "hata", "ilerleme": (d / "hata.txt").read_text("utf-8").strip()}
        if (d / "koken-hatasi").exists():  # eklenti düğmesi ?cevir=yeniden ile baştan çevirmeyi önerir (R6-01)
            h["yeniden_cevir"] = True
        return h
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
    if n := len(ortak.json_oku(d / "parcalar.json") or []):  # yarım/bozuk okunursa aşağıdaki genel metinler
        cev = len(ortak.json_oku(d / "ceviri.json") or {})
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
        if not ortak.kilitli(IS / ".gpu-kilit"):
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
            if p := ortak.json_oku(IS / a[1] / "parcalar.json"):
                oranlar.append(dk / (p[-1]["son"] / 60))
    return sorted(oranlar)[len(oranlar) // 2] if oranlar else 1.5


def bilgi(vid, sure_sn):
    """Eklentinin bilgi paneli: bu video için ne durumda, ne kadar sürer, önünde ne var."""
    b = durum(vid)
    k = hiz_katsayisi()
    b["katsayi"] = round(k, 2)
    if sure_sn:
        b["tahmin_dk"] = round(2 + sure_sn / 60 * k)  # +2 dk: modellerin yüklenmesi, kısa videoda belirgin
    # bu videonun hangi modelle çevrildiği (cevir.py yazar; eski işlerde yok, yarım/bozuksa da yok sayılır)
    b["model"] = (ortak.json_oku(IS / vid / "uretim.json") or {}).get("model")
    b["yeni_model"] = ortak.ayar()["ceviri"]["model"]  # tepsiden değişebilir, her soruda dosyadan okunur
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

    def _yetkili(self, u):
        """Yalnız bu bilgisayarın adı (DNS yeniden bağlamayla gelen yabancı alan adı reddedilir) ve doğru belirteç;
        ses adresinde belirteç yerine o videoya özel bilet. Bayt olarak karşılaştırılır: ASCII dışı ya da bozuk
        girdi de bağlantıyı koparmadan 401 alır (R6-04; compare_digest ASCII dışı str'de hata verir)."""
        esit = lambda a, b: hmac.compare_digest(a.encode(), b.encode())
        if self.headers.get("Host") not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            return False
        if m := re.fullmatch(r"/ses/([\w-]{11})\.m4a", u.path):
            return esit(parse_qs(u.query).get("b", [""])[0], ortak.ses_bileti(m[1]))
        return esit(self.headers.get("X-TR-Belirtec", ""), BELIRTEC)

    def _hazirsa_bilet(self, vid, d):
        if d.get("durum") == "hazir":
            d["bilet"] = ortak.ses_bileti(vid)
        return self._json(d)

    def _guvenli(self, f):
        """Beklenmeyen hata bağlantıyı cevapsız koparmasın: JSON 500 (ayrıntı sunucu günlüğüne)."""
        u = urlparse(self.path)
        try:
            if not self._yetkili(u):
                return self._json({"hata": "yetki"}, 401)
            f(u)
        except (BrokenPipeError, ConnectionError):
            pass  # eklenti isteği bırakmış (ör. ses sarılırken), cevap verecek kimse yok
        except Exception as e:
            traceback.print_exc()
            try:
                self._json({"hata": f"sunucu hatası: {type(e).__name__}"}, 500)
            except OSError:
                pass

    def do_GET(self):
        self._guvenli(self._get)

    def do_POST(self):
        self._guvenli(self._post)

    def _get(self, u):
        if m := re.fullmatch(r"/durum/([\w-]{11})", u.path):
            return self._hazirsa_bilet(m[1], durum(m[1]))
        if m := re.fullmatch(r"/bilgi/([\w-]{11})", u.path):
            try:
                sure = float(parse_qs(u.query).get("sure", ["0"])[0] or 0)
            except ValueError:
                sure = math.nan
            if not 0 <= sure <= AZAMI_SURE:  # NaN, sonsuz, negatif de buraya düşer
                return self._json({"hata": "geçersiz süre"}, 400)
            return self._hazirsa_bilet(m[1], bilgi(m[1], sure))
        if m := re.fullmatch(r"/ses/([\w-]{11})\.m4a", u.path):
            return self._ses(IS / m[1] / f"turkce-{motor(m[1])}.m4a")
        self._json({"hata": "bilinmeyen adres"}, 404)

    def _ses(self, f):
        """Tek aralıklı Range: son dosya sonuna kırpılır; karşılanamaz/ters/bozuk/çok aralıklı istek 416 (G03).
        Dosya 64 KB'lık parçalarla yazılır, belleğe tek seferde okunmaz."""
        if not f.exists():
            return self._json({"hata": "ses yok"}, 404)
        boy = f.stat().st_size
        bas, son = 0, boy - 1
        if (rng := self.headers.get("Range")) is not None:
            r = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
            if r and r[1]:  # bas-[son]
                bas = int(r[1])
                son = min(int(r[2]), boy - 1) if r[2] else boy - 1
                gecerli = not r[2] or int(r[2]) >= bas  # ters aralık geçersiz
            elif r and r[2]:  # sonek: son N bayt (N=0 karşılanamaz)
                bas, gecerli = max(0, boy - int(r[2])), int(r[2]) > 0
            else:
                gecerli = False
            if not gecerli or bas >= boy:  # boş dosya da buraya düşer
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{boy}")
                self.send_header("Content-Length", "0")
                return self.end_headers()
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
            kalan = son - bas + 1
            while kalan > 0 and (parca := h.read(min(65536, kalan))):
                self.wfile.write(parca)
                kalan -= len(parca)

    def _post(self, u):
        if m := re.fullmatch(r"/hazirla/([\w-]{11})", u.path):
            vid, q = m[1], parse_qs(u.query)
            with baslatma_kilidi:
                if (d := durum(vid))["durum"] in ("hazir", "hazirlaniyor", "turkce"):
                    return self._json(d)
                for v in [v for v, p in surecler.items() if p.poll() is not None]:
                    del surecler[v]  # bitmiş işler sayılmaz
                if len(surecler) >= AZAMI_IS:
                    return self._json({"durum": "dolu", "ilerleme": f"Aynı anda en çok {AZAMI_IS} video hazırlanır; "
                                       "biri bitince yeniden bas."}, 429)
                (IS / vid / "hata.txt").unlink(missing_ok=True)  # hata sonrası yeniden deneme
                (IS / vid / "koken-hatasi").unlink(missing_ok=True)
                (IS / vid).mkdir(parents=True, exist_ok=True)
                ek = ["--yeniden-cevir"] if q.get("cevir") == ["yeniden"] else []
                with open(IS / vid / "gunluk.txt", "w", encoding="utf-8") as gunluk:  # süreç kendi kopyasını tutar
                    surecler[vid] = subprocess.Popen(
                        [sys.executable, str(ortak.KOK / "cevir.py"), vid, "--ad", q.get("ad", [vid])[0], "--oncelik", *ek],
                        stdout=gunluk, stderr=subprocess.STDOUT)
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
    try:
        sunucu = ThreadingHTTPServer(("127.0.0.1", port), Isleyici)
    except OSError as e:
        sys.exit(f"Port {port} kullanımda ya da açılamadı ({e}). Başka bir program ya da açık bir Lokal Dublaj olabilir.")
    sunucu.serve_forever()

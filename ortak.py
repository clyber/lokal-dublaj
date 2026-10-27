"""Ortak parçalar: ayar dosyası, video kimliği, ekran kartı sırası, çeviri modeli (cevir.py, sunucu.py, toplu.py,
baslatici.py kullanır)."""
import hmac, json, os, re, secrets, sys, time, tomllib, urllib.error, urllib.request
from pathlib import Path

KOK = Path(__file__).parent

# Ayar dosyası yoksa ya da bir alan eksikse bunlar geçerli (ayarlar.ornek.toml ile aynı).
VARSAYILAN = {
    "hedef_dil": "tr",
    "cikti_klasoru": "",            # boş: mp4 üretilmez/taşınmaz; video.mp4_uret açıksa buraya taşınır
    "calisma_klasoru": "",          # boş: uygulama klasörü/is
    "model_klasoru": "",            # boş: Hugging Face'in kendi önbelleği
    "js_ortami": "node",            # yt-dlp'nin YouTube için istediği JavaScript ortamı: node ya da deno
    "ceviri": {"adres": "http://localhost:1234/v1", "model": "", "grup_boyu": 20},
    "ses": {"motor": "ema", "piper_sesi": "", "ozgun_seviye": 0.15, "azami_hizlandirma": 1.35},
    "video": {"mp4_uret": False, "azami_yukseklik": 720},
    "yaziya_dokme": {"model": "mobiuslabsgmbh/faster-whisper-large-v3-turbo"},
    "sunucu": {"port": 8799},
}


def ayar():
    """ayarlar.toml'u varsayılanların üstüne bindirir; dosya yoksa varsayılanlar."""
    a = {k: (dict(v) if isinstance(v, dict) else v) for k, v in VARSAYILAN.items()}
    f = KOK / "ayarlar.toml"
    if f.exists():
        for k, v in tomllib.loads(f.read_text("utf-8")).items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                a[k].update(v)
            else:
                a[k] = v
    a["calisma_klasoru"] = Path(a["calisma_klasoru"] or KOK / "is")
    if a["model_klasoru"]:
        os.environ.setdefault("HF_HOME", a["model_klasoru"])
    return a


def video_id(s):
    """watch?v=, youtu.be/, shorts/, embed/ bağlantılarından ya da çıplak kimlikten 11 karakterlik kimliği çıkarır."""
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})", s) or re.fullmatch(r"([\w-]{11})", s.strip())
    if not m:
        raise ValueError(f"YouTube video kimliği bulunamadı: {s}")
    return m.group(1)


def kilit_dene(f):
    """Dosyanın ilk baytına işletim sistemi kilidi koymayı dener; süreç ölünce kilit kendiliğinden kalkar."""
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def kilit_birak(f):
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def kilitli(f):
    """Bu kilit dosyasını yaşayan bir süreç tutuyor mu (dosya yoksa hayır). Video kilidi (.is-kilit): iş sürüyor mu."""
    if not f.exists():
        return False
    with open(f, "a+") as h:
        if kilit_dene(h):
            kilit_birak(h)
            return False
    return True


def json_oku(f):
    """JSON dosyası; yoksa ya da yarım/bozuksa None (okuyan çökmesin, R6-07)."""
    try:
        return json.loads(Path(f).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def json_yaz(f, veri):
    """Atomik yazım: geçici dosya, sonra tek hamlede değiştir; okuyan yarım dosya görmez, kesinti yarım kayıt bırakmaz.
    Windows'ta o an dosyayı okuyan varsa değiştirme kısa süre reddedilir: birkaç kez yeniden denenir."""
    gecici = Path(f).with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1), "utf-8")
    for i in range(20):
        try:
            return gecici.replace(f)
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.05)


def gpu_kilidi(is_kok, oncelik=False):
    """Aynı anda tek video ekran kartında. Eklentiden gelen istek (oncelik) bekliyorsa toplu işin sıradakisi yol verir."""
    f = open(is_kok / ".gpu-kilit", "a+")
    while True:
        bekleyen = [o for o in is_kok.glob(".oncelik-*") if time.time() - o.stat().st_mtime < 3 * 3600]
        if (oncelik or not bekleyen) and kilit_dene(f):
            return f
        print("Ekran kartı meşgul, sıra bekleniyor…", flush=True)
        time.sleep(10)


def cuda_dll_yolu():
    """Windows'ta pip ile gelen CUDA kitaplıklarını (cublas, cudnn) bulunur kılar; Linux'ta gerek yok."""
    if os.name != "nt":
        return
    for alt in ("cublas", "cudnn", "cuda_nvrtc"):
        d = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / alt / "bin"
        if d.exists():
            os.add_dll_directory(str(d))
            os.environ["PATH"] = str(d) + os.pathsep + os.environ["PATH"]


def belirtec():
    """Kurulum başına gizli belirteç (ilk çağrıda üretilir, KOK/.belirtec, git dışı). Sunucu her istekte ister; eklenti
    onu yalnız köprüden alır (Firefox o kanalı yalnız bu eklentiye açar), tepsi dosyadan okur. Sıradan bir web sayfası
    ya da başka bir program onu bilmeden iş başlatamaz, durum ya da ses okuyamaz."""
    f = KOK / ".belirtec"
    try:  # aynı anda iki süreç üretmeye kalkarsa yalnız biri yazar (O_EXCL), öteki onunkini okur
        fd = os.open(f, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as h:
            h.write(secrets.token_urlsafe(32))
    except FileExistsError:
        pass
    for _ in range(50):
        if b := f.read_text().strip():
            return b
        time.sleep(0.02)
    # 1 sn sonra hâlâ boş: üreten süreç yazamadan ölmüş. Yeniden üret, atomik yerleştir, dosyada kalanı döndür.
    # Sınır: tam bu anda iki süreç birden yeniden üretirse biri eski değeri tutabilir; sunucuyu yeniden açmak düzeltir.
    gecici = f.with_name(f".belirtec.{os.getpid()}.tmp")
    gecici.write_text(secrets.token_urlsafe(32))
    gecici.replace(f)
    return f.read_text().strip()


def ses_bileti(vid):
    """Tek videonun sesini okumaya yarayan bilet: Audio nesnesi başlık gönderemediği için adrese eklenir; asıl
    belirteç adrese hiç yazılmaz, bilet de yalnız o videoyu açar."""
    return hmac.new(belirtec().encode(), vid.encode(), "sha256").hexdigest()[:32]


class Hata(Exception):
    """Kullanıcıya gösterilecek, açıklaması belli hata (cevir.py bunu hata.txt'ye, tepsi bildirime yazar).
    yeniden_cevir: kurtarma yolu baştan çevirmek (eklentinin düğmesi POST /hazirla/<id>?cevir=yeniden gönderir)."""
    def __init__(self, mesaj, yeniden_cevir=False):
        super().__init__(mesaj)
        self.yeniden_cevir = yeniden_cevir


def _json(url, govde=None, sure=5):
    r = urllib.request.Request(url, json.dumps(govde).encode() if govde else None, {"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=sure) as y:
        return json.loads(y.read())


def model_listesi(adres):
    """Çeviri sunucusundaki sohbet modelleri: [(kimlik, bellekte mi)]. LM Studio'nun /api/v1/models'i türü ve bellekte
    olup olmadığını söyler (JIT açıkken listede indirilmiş ama yüklenmemiş modeller de var); başka sunucuda
    (Ollama vb.) OpenAI uyumlu /v1/models'e düşülür, bellek durumu None. Sunucu kapalıysa Hata."""
    adres = adres.rstrip("/")
    try:
        return [(m["key"], bool(m.get("loaded_instances")))
                for m in _json(re.sub(r"/v1$", "", adres) + "/api/v1/models")["models"] if m.get("type") == "llm"]
    except Exception:
        pass
    try:
        return [(m["id"], None) for m in _json(adres + "/models")["data"] if "embed" not in m["id"].lower()]
    except Exception:
        raise Hata(f"Çeviri sunucusu kapalı ({adres}). LM Studio'yu açıp Developer → Start Server de (ya da Ollama'yı başlat).")


def ceviri_istemi(grup, onceki):
    """grup: [{id, bas, son, metin}] → modelden her parça için `id<TAB>çeviri` satırı isteyen istem."""
    satirlar = "\n".join(f'{x["id"]}\t{x["son"] - x["bas"]:.1f}sn\t{x["metin"]}' for x in grup)
    return ("Aşağıdaki video konuşma parçalarını doğal, akıcı, konuşma dilinde Türkçeye çevir. "
            "Her parça yanında verilen saniyede SESLİ okunabilecek kadar kısa olsun; anlamı koru, sayı ve birimleri koru, "
            "teknik terimleri Türkçede yaygın hâliyle yaz. Çıktı: her parça için TEK satır, biçim `id<TAB>çeviri`; "
            "başka hiçbir şey yazma (açıklama, JSON, kod bloğu yok).\n"
            f"Önceki bağlam: {onceki}\n\nid\tsüre\tmetin\n{satirlar}")


def ceviri_sor(adres, model, mesaj):
    """Modelin cevabı; düşünme bloğu (<think>…</think>) atılır. Sunucu reddederse sebebiyle Hata."""
    try:
        y = _json(adres.rstrip("/") + "/chat/completions",
                  {"model": model, "temperature": 0.2, "messages": [{"role": "user", "content": mesaj}]}, sure=600)
    except urllib.error.HTTPError as e:  # sunucunun söylediği sebebi kaybetme (ör. bağlam penceresi aşıldı)
        raise Hata(f"Çeviri sunucusu isteği reddetti ({e.code}): {e.read().decode('utf-8', 'replace')[:300]}") from e
    return re.sub(r"<think>.*?</think>", "", y["choices"][0]["message"]["content"], flags=re.S)


def cevap_coz(cevap, istenen):
    """`id<TAB>çeviri` satırlarından istenen kimliklerin boş olmayan çevirileri."""
    return {k: v.strip() for k, v in re.findall(r"^\s*(\d+)\s*[\t:|-]\s*(.+?)\s*$", cevap, flags=re.M)
            if k in istenen and v.strip()}


# Model seçilirken gerçek istem biçimiyle 3 cümle: olumsuzluk, sayı+birim, teknik terim
DENEME = [{"id": 0, "bas": 0, "son": 2.5, "metin": "Do not exceed 12 volts."},
          {"id": 1, "bas": 2.5, "son": 5.5, "metin": "Tighten the screw to 0.8 newton metres."},
          {"id": 2, "bas": 5.5, "son": 8.5, "metin": "The fan stays on after the motor stops."}]


def deneme_cevirisi(adres, model):
    """Model biçime uyuyor ve sayıları koruyor mu: {id: çeviri} ya da Hata. Kalite garantisi değil, temel uyum denetimi."""
    tr = cevap_coz(ceviri_sor(adres, model, ceviri_istemi(DENEME, "")), {"0", "1", "2"})
    if len(tr) < 3:
        raise Hata(f"model istenen biçimde cevap vermedi ({len(tr)}/3 satır)")
    if "12" not in tr["0"] or not re.search(r"0[.,]8", tr["1"]):
        raise Hata(f"model sayıları korumadı: {tr['0']} / {tr['1']}")
    return tr


def model_kaydet(model):
    """ayarlar.toml'da [ceviri] model satırının yalnız değerini değiştirir; dosyanın geri kalanı, satırın girintisi ve
    yorumu olduğu gibi kalır. Çift/tek tırnaklı değer, girintili satır, bölümsüz dosya desteklenir. Dosya yoksa örnekten
    kopyalanır. Sonuç yazmadan önce TOML olarak doğrulanır; yazım atomik (yarım dosya kalmaz)."""
    f = KOK / "ayarlar.toml"
    metin = f.read_text("utf-8") if f.exists() else (KOK / "ayarlar.ornek.toml").read_text("utf-8")
    deger = json.dumps(model, ensure_ascii=False)  # JSON dizgisi geçerli bir TOML temel dizgisidir
    satirlar = metin.splitlines(keepends=True)
    bas, son = None, len(satirlar)  # [ceviri] başlığının satırı, bölümün bittiği satır
    for i, s in enumerate(satirlar):
        if re.match(r"\s*\[", s):
            if bas is not None:
                son = i
                break
            if re.match(r"\s*\[\s*ceviri\s*\]\s*(#.*)?$", s):
                bas = i
    if bas is None:
        metin = metin.rstrip("\n") + f"\n\n[ceviri]\nmodel = {deger}\n"
    else:
        anahtar = re.compile(r"""(\s*(?:model|"model"|'model')\s*=\s*)("(?:[^"\\\n]|\\.)*"|'[^'\n]*')""")
        for i in range(bas + 1, son):
            if m := anahtar.match(satirlar[i]):
                satirlar[i] = m[1] + deger + satirlar[i][m.end():]
                break
        else:
            if not satirlar[bas].endswith("\n"):
                satirlar[bas] += "\n"
            satirlar.insert(bas + 1, f"model = {deger}\n")
        metin = "".join(satirlar)
    try:
        tamam = tomllib.loads(metin).get("ceviri", {}).get("model") == model
    except tomllib.TOMLDecodeError:
        tamam = False
    if not tamam:
        raise Hata("ayar dosyası güncellenemedi (beklenmeyen biçim)")
    gecici = f.with_suffix(".tmp")
    gecici.write_text(metin, "utf-8")
    gecici.replace(f)


if __name__ == "__main__":  # küçük öz denetim: python ortak.py
    for u in ("https://www.youtube.com/watch?v=Zko_s2LO9Wo&list=x", "https://youtu.be/Zko_s2LO9Wo?t=3",
              "https://www.youtube.com/shorts/Zko_s2LO9Wo", "Zko_s2LO9Wo"):
        assert video_id(u) == "Zko_s2LO9Wo", u
    try:
        video_id("https://example.com/abc")
        raise AssertionError("geçersiz bağlantı kabul edildi")
    except ValueError:
        pass
    a = ayar()
    assert a["ses"]["motor"] in ("ema", "chatterbox", "piper") and a["sunucu"]["port"] > 0
    print("ortak.py denetimi geçti:", a["ses"]["motor"], a["sunucu"]["port"], a["calisma_klasoru"])

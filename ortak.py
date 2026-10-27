"""Ortak parçalar: ayar dosyası, video kimliği, ekran kartı sırası (cevir.py, sunucu.py, toplu.py kullanır)."""
import os, re, sys, time, tomllib
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

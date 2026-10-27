"""Bir YouTube videosunu yerelde Türkçe seslendirir.

Akış: yt-dlp (ses; istenirse video) -> faster-whisper (yazıya dök) -> LM Studio/Ollama (çevir)
-> EMA Lightning / Chatterbox / Piper (Türkçe ses) -> zaman çizelgesine yerleştir -> turkce-<motor>.m4a
(video.mp4_uret açıksa özgün ses kısık + Türkçe ses -> mp4). Ayarlar: ayarlar.toml (bkz. ayarlar.ornek.toml).
Kullanım: python cevir.py <youtube-bağlantısı> [--ses ema|chatterbox|piper] [--ad "dosya adı"] [--oncelik]
Ara sonuçlar <calisma_klasoru>/<video-id>/ altında; her adımın dosyası varsa atlanır (yeniden koşmak ucuz).
Hata olursa <video-id>/hata.txt yazılır; eklenti bunu gösterir, yeniden basınca silinip baştan denenir.
"""
import argparse, json, re, subprocess, sys, time, urllib.error, urllib.request, wave
from pathlib import Path

import ortak

A = ortak.ayar()
IS = A["calisma_klasoru"]
ortak.cuda_dll_yolu()
ORNEK_PIPER = 22050  # Piper orta kalite seslerin örnekleme hızı


class Hata(Exception):
    """Kullanıcıya gösterilecek, açıklaması belli hata (hata.txt'ye bu metin yazılır)."""


def kos(*a):
    subprocess.run(a, check=True)


def indirme_bekle(d, hedef, bayat_sn=120, aralik=10):
    """toplu.py'nin önden indiricisi bu videoyu indiriyorsa bitmesini bekler. Yarım dosyalar bayat_sn boyunca
    hiç büyümediyse indirici ölmüş sayılır, yarım dosyalar silinir (K02: eskiden sonsuza kadar bekliyordu).
    Döner: hedef dosya hazır mı."""
    while not hedef.exists():
        yarim = list(d.glob("*.part")) + list(d.glob("video.f*"))
        if not yarim:
            return False
        if time.time() - max(f.stat().st_mtime for f in yarim) > bayat_sn:
            for f in yarim:
                f.unlink(missing_ok=True)
            return False
        time.sleep(aralik)
    return True


def indir(url, d):
    """Sesi (mp4 üretilecekse videoyu da) indirir, yazıya dökme için 16 kHz tek kanal wav çıkarır."""
    mp4 = A["video"]["mp4_uret"]
    hedef = d / ("video.mp4" if mp4 else "ses.m4a")
    indirme_bekle(d, hedef)
    if not hedef.exists():
        bicim = (f"bv*[height<={A['video']['azami_yukseklik']}][ext=mp4]+ba[ext=m4a]/b[height<={A['video']['azami_yukseklik']}]"
                 if mp4 else "ba[ext=m4a]/ba")
        ek = ["--merge-output-format", "mp4"] if mp4 else []
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "--js-runtimes", A["js_ortami"],
                            "-f", bicim, *ek, "-o", str(hedef), url])
        if r.returncode or not hedef.exists():
            raise Hata("Video indirilemedi (yt-dlp). İnternet bağlantısını kontrol et; sürerse yt-dlp'yi güncelle: .venv\\Scripts\\pip install -U \"yt-dlp[default]\"")
    a = d / "ses16k.wav"
    if not a.exists():
        kos("ffmpeg", "-y", "-loglevel", "error", "-i", str(hedef), "-ac", "1", "-ar", "16000", str(a))
    return hedef, a


def yaziya_dok(a, d):
    f = d / "parcalar.json"
    if f.exists():
        return json.loads(f.read_text("utf-8"))
    import numpy as np
    from faster_whisper import WhisperModel
    try:
        m = WhisperModel(A["yaziya_dokme"]["model"], device="cuda", compute_type="float16")
    except Exception as e:
        raise Hata(f"Konuşma tanıma modeli ekran kartında açılamadı (CUDA): {e}")
    with wave.open(str(a)) as wf:  # av sürüm uyumsuzluğu yüzünden sesi kendimiz veriyoruz
        ses = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    segs, info = m.transcribe(ses, vad_filter=True, beam_size=5)
    p = [{"id": i, "bas": round(s.start, 2), "son": round(s.end, 2), "metin": s.text.strip()} for i, s in enumerate(segs)]
    if not p:
        raise Hata("Videoda konuşma bulunamadı.")
    print(f"dil={info.language} parca={len(p)}")
    (d / "dil.txt").write_text(info.language, "utf-8")
    f.write_text(json.dumps(p, ensure_ascii=False, indent=1), "utf-8")
    return p


def ceviri_modeli():
    """Çeviri sunucusu açık mı bak; ayarda model yoksa sunucudaki ilk sohbet modelini seç."""
    adres = A["ceviri"]["adres"].rstrip("/")
    try:
        with urllib.request.urlopen(adres + "/models", timeout=5) as y:
            modeller = [m["id"] for m in json.loads(y.read())["data"]]
    except Exception:
        raise Hata(f"Çeviri sunucusu kapalı ({adres}). LM Studio'yu açıp Developer → Start Server de (ya da Ollama'yı başlat).")
    if A["ceviri"]["model"]:
        return A["ceviri"]["model"]
    sohbet = [m for m in modeller if "embed" not in m]
    if not sohbet:
        raise Hata("Çeviri sunucusunda yüklü model yok. LM Studio'da bir model indir (öneri: gemma-4-12b-it).")
    return sohbet[0]


def ceviri_sor(model, mesaj):
    govde = {"model": model, "temperature": 0.2, "messages": [{"role": "user", "content": mesaj}]}
    r = urllib.request.Request(A["ceviri"]["adres"].rstrip("/") + "/chat/completions", json.dumps(govde).encode(),
                               {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=600) as y:
            return json.loads(y.read())["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:  # sunucunun söylediği sebebi kaybetme (ör. bağlam penceresi aşıldı)
        raise Hata(f"Çeviri sunucusu isteği reddetti ({e.code}): {e.read().decode('utf-8', 'replace')[:300]}") from e


def cevir(p, d, model):
    f = d / "ceviri.json"
    tr = json.loads(f.read_text("utf-8")) if f.exists() else {}
    n = A["ceviri"]["grup_boyu"]
    def grup_cevir(grup, onceki):
        satirlar = "\n".join(f'{x["id"]}\t{x["son"] - x["bas"]:.1f}sn\t{x["metin"]}' for x in grup)
        istem = (
            "Aşağıdaki video konuşma parçalarını doğal, akıcı, konuşma dilinde Türkçeye çevir. "
            "Her parça yanında verilen saniyede SESLİ okunabilecek kadar kısa olsun; anlamı koru, sayı ve birimleri koru, "
            "teknik terimleri Türkçede yaygın hâliyle yaz. Çıktı: her parça için TEK satır, biçim `id<TAB>çeviri`; "
            "başka hiçbir şey yazma (açıklama, JSON, kod bloğu yok).\n"
            f"Önceki bağlam: {onceki}\n\nid\tsüre\tmetin\n{satirlar}"
        )
        try:
            cevap = re.sub(r"<think>.*?</think>", "", ceviri_sor(model, istem), flags=re.S)
        except Hata as e:
            # modelin bağlam penceresi dolduysa (LM Studio paralel yuvalarda pencereyi bölüyor) grubu ikiye ayır
            if "Context size" in str(e) and len(grup) > 1:
                y = len(grup) // 2
                return {**grup_cevir(grup[:y], onceki), **grup_cevir(grup[y:], "")}
            raise
        istenen = {str(x["id"]) for x in grup}
        return {k: v.strip() for k, v in re.findall(r"^\s*(\d+)\s*[\t:|-]\s*(.+?)\s*$", cevap, flags=re.M)
                if k in istenen and v.strip()}

    for tur in range(3):  # eksik kalan gruplar sonraki turda yeniden istenir
        for i in range(0, len(p), n):
            grup = [x for x in p[i:i + n] if str(x["id"]) not in tr]
            if not grup:
                continue
            yeni = grup_cevir(grup, " ".join(x["metin"] for x in p[max(0, i - 5):i]))
            if not yeni:
                print("UYARI: çeviri çözülemedi, grup sonraki turda yeniden istenecek")
                continue
            tr.update(yeni)
            gecici = f.with_suffix(".tmp")  # yarım dosyayı sunucu okumasın: yaz, sonra tek hamlede değiştir
            gecici.write_text(json.dumps(tr, ensure_ascii=False, indent=1), "utf-8")
            gecici.replace(f)
            print(f"çeviri {len(tr)}/{len(p)}")
    eksik = [x["id"] for x in p if str(x["id"]) not in tr]
    if eksik:  # eksik cümleyle "hazır" demek, dinleyene bazı cümleleri hiç duyurmamak demek (K01)
        raise Hata(f"Çevirinin {len(eksik)}/{len(p)} parçası alınamadı. Yeniden dene (alınanlar saklı); sürerse çeviri modelini değiştir.")
    return tr


def seslendir(p, tr, d, motor):
    import numpy as np, soundfile as sf, librosa
    sd = d / f"tts-{motor}"
    sd.mkdir(exist_ok=True)
    uret = None
    if motor == "ema":  # EMA Lightning: tek Türkçe ses, çok hızlı; toplu üretim
        from ema_lightning import EMA
        tts = EMA()
        sr = 48000
        eksik = [x for x in p if tr.get(str(x["id"]), "").strip() and not (sd / f'{x["id"]}.wav').exists()]
        for i in range(0, len(eksik), 32):
            grup = eksik[i:i + 32]
            for x, s in zip(grup, tts.say([tr[str(x["id"])].strip() for x in grup])):
                sf.write(sd / f'{x["id"]}.wav', s.audio, s.sample_rate)
            print(f"ses {min(i + 32, len(eksik))}/{len(eksik)}", flush=True)
    elif motor == "chatterbox":  # konuşmacının kendi sesinden 12 sn örnekle ona benzer Türkçe ses
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        cb = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
        ref = d / "referans.wav"
        if not ref.exists():
            kos("ffmpeg", "-y", "-loglevel", "error", "-ss", "2", "-t", "12", "-i", str(d / "ses16k.wav"), "-ar", "24000", str(ref))
        sr = cb.sr
        uret = lambda m, w: sf.write(w, cb.generate(m, language_id=A["hedef_dil"], audio_prompt_path=str(ref)).squeeze().cpu().numpy(), sr)
    else:
        if not A["ses"]["piper_sesi"]:
            raise Hata("Piper seçili ama ayarlar.toml'da ses.piper_sesi (.onnx yolu) boş.")
        from piper import PiperVoice
        ses = PiperVoice.load(A["ses"]["piper_sesi"])
        sr = ORNEK_PIPER
        def uret(m, w):
            with wave.open(str(w), "wb") as wf:
                ses.synthesize_wav(m, wf)
    toplam = int((p[-1]["son"] + 5) * sr)
    iz = np.zeros(toplam, dtype=np.float32)
    for i, x in enumerate(p):
        metin = tr.get(str(x["id"]), "").strip()
        if not metin:
            continue
        w = sd / f'{x["id"]}.wav'
        if not w.exists():
            uret(metin, w)
        a = sf.read(str(w), dtype="float32")[0]
        # yuva: bu parçanın başından bir sonrakinin başına kadar; sığmıyorsa ses perdesini bozmadan hızlandır
        yuva = max((p[i + 1]["bas"] if i + 1 < len(p) else x["son"] + 3) - x["bas"], 0.5)
        hiz = len(a) / sr / yuva
        if hiz > 1.0:
            a = librosa.effects.time_stretch(a, rate=min(hiz, A["ses"]["azami_hizlandirma"]))
        b = int(x["bas"] * sr)
        e = min(b + len(a), toplam)
        iz[b:e] += a[: e - b]
    yol = d / f"turkce-{motor}.wav"
    sf.write(str(yol), np.clip(iz, -1, 1), sr)
    return yol


def bitir(d, kaynak, t, motor, ad):
    """Türkçe sesi küçük m4a yap (eklenti bunu çalar); mp4 istenmişse üretip çıktı klasörüne taşı; ara dosyaları sil.
    Geriye kalan: parcalar.json, ceviri.json, dil.txt, turkce-<motor>.m4a, bitti-<motor> (birkaç MB)."""
    import shutil
    kos("ffmpeg", "-y", "-loglevel", "error", "-i", str(t), "-c:a", "aac", "-b:a", "96k", str(t.with_suffix(".m4a")))
    sonuc = t.with_suffix(".m4a")
    if A["video"]["mp4_uret"]:
        mp4 = d / f"video-turkce-{motor}.mp4"
        kos("ffmpeg", "-y", "-loglevel", "error", "-i", str(kaynak), "-i", str(t), "-filter_complex",
            f"[0:a]volume={A['ses']['ozgun_seviye']}[o];[1:a]aresample=48000,volume=1.6[t];[o][t]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(mp4))
        if A["cikti_klasoru"]:
            hedef = Path(A["cikti_klasoru"])
            hedef.mkdir(parents=True, exist_ok=True)
            sonuc = hedef / (re.sub(r'[<>:"/\\|?*]', "", ad).strip() + ".mp4")
            sonuc.unlink(missing_ok=True)
            shutil.move(str(mp4), str(sonuc))
        else:
            sonuc = mp4
    for f in [kaynak, d / "ses16k.wav", d / "referans.wav", *d.glob("*.wav")]:
        f.unlink(missing_ok=True)
    for s in d.glob("tts*"):
        shutil.rmtree(s, ignore_errors=True)
    (d / f"bitti-{motor}").write_text(str(sonuc), "utf-8")
    return sonuc


def calis(g, vid, d):
    kaynak, a = indir(g.url, d)
    kilit = ortak.gpu_kilidi(IS, g.oncelik)  # süreç bitene kadar tutulur
    (IS / ".calisan").write_text(json.dumps({"vid": vid, "ad": g.ad or vid}, ensure_ascii=False), "utf-8")
    p = yaziya_dok(a, d)
    if (d / "dil.txt").exists() and (d / "dil.txt").read_text("utf-8") == A["hedef_dil"]:
        (d / "zaten-turkce").touch()
        for f in (kaynak, a):
            f.unlink(missing_ok=True)
        print("Video zaten hedef dilde, işlem yok.")
        return None
    tr = cevir(p, d, ceviri_modeli())
    t = seslendir(p, tr, d, g.ses)
    return bitir(d, kaynak, t, g.ses, g.ad or vid)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--ses", choices=["ema", "chatterbox", "piper"], default=A["ses"]["motor"])
    ap.add_argument("--ad", help="mp4 üretilirse çıktı dosyasının adı (uzantısız)")
    ap.add_argument("--oncelik", action="store_true", help="eklentiden gelen istek: toplu işin önüne geçer")
    g = ap.parse_args()
    vid = ortak.video_id(g.url)
    g.url = f"https://www.youtube.com/watch?v={vid}"
    d = IS / vid
    d.mkdir(parents=True, exist_ok=True)
    # video kilidi: aynı video için tek süreç (K06); süreç ölünce kendiliğinden kalkar, sunucu buna bakıp
    # "hazırlanıyor" ile "yarıda kalmış"ı ayırır (K03)
    is_kilidi = open(d / ".is-kilit", "a+")
    if not ortak.kilit_dene(is_kilidi):
        print("Bu video zaten hazırlanıyor, ikinci iş açılmadı.")
        raise SystemExit(0)
    (d / "hata.txt").unlink(missing_ok=True)
    isaret = IS / f".oncelik-{vid}"
    if g.oncelik:
        isaret.touch()
    try:
        print("HAZIR:", calis(g, vid, d))
    except Exception as e:
        mesaj = str(e) if isinstance(e, Hata) else f"Beklenmeyen hata: {type(e).__name__}: {e}"
        (d / "hata.txt").write_text(mesaj, "utf-8")
        print("HATA:", mesaj, file=sys.stderr)
        raise SystemExit(1)
    finally:
        isaret.unlink(missing_ok=True)

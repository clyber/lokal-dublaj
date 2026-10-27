"""Bir YouTube oynatma listesinin tamamını sırayla seslendirir (önden hazırlık).

Kullanım: python toplu.py <oynatma-listesi-bağlantısı> [--ses ema|chatterbox|piper]
Her video ayrı süreçte işlenir (ekran kartı belleği her videodan sonra boşalır); biten video atlanır,
hata veren bir kez yeniden denenir. Durum: <calisma_klasoru>/toplu-durum.tsv (sıra, id, sonuç, saat, süre, başlık).
"""
import argparse, subprocess, sys, time

import ortak

A = ortak.ayar()
IS = A["calisma_klasoru"]

ap = argparse.ArgumentParser()
ap.add_argument("liste")
ap.add_argument("--ses", default=A["ses"]["motor"])
g = ap.parse_args()

satirlar = subprocess.run(
    [sys.executable, "-m", "yt_dlp", "--flat-playlist", "--js-runtimes", A["js_ortami"],
     "--print", "%(playlist_index)s|%(id)s|%(title)s", g.liste],
    capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip().splitlines()
IS.mkdir(parents=True, exist_ok=True)
durum = IS / "toplu-durum.tsv"

bitmis = lambda v: any((IS / v).glob("bitti-*")) or (IS / v / "zaten-turkce").exists()  # hangi sesle olursa olsun
bekleyen = [s.split("|")[1] for s in satirlar if not bitmis(s.split("|")[1])]
# internet yavaşsa: ilk bekleyen hariç (onu cevir.py indirir) diğerlerini arkada sırayla önden indir
if len(bekleyen) > 1:
    (IS / "onden-indir.txt").write_text("\n".join(f"https://www.youtube.com/watch?v={v}" for v in bekleyen[1:]), "utf-8")
    yuk = A["video"]["azami_yukseklik"]
    bicim = (["-f", f"bv*[height<={yuk}][ext=mp4]+ba[ext=m4a]/b[height<={yuk}]", "--merge-output-format", "mp4",
              "-o", str(IS / "%(id)s" / "video.mp4")] if A["video"]["mp4_uret"]
             else ["-f", "ba[ext=m4a]/ba", "-o", str(IS / "%(id)s" / "ses.m4a")])
    subprocess.Popen([sys.executable, "-m", "yt_dlp", "--js-runtimes", A["js_ortami"], "--no-playlist", *bicim,
                      "-a", str(IS / "onden-indir.txt")],
                     stdout=open(IS / "onden-indir.log", "w"), stderr=subprocess.STDOUT)

for satir in satirlar:
    sira, vid, baslik = satir.split("|", 2)
    if bitmis(vid):
        continue
    for deneme in (1, 2):
        t = time.time()
        r = subprocess.run([sys.executable, str(ortak.KOK / "cevir.py"), vid, "--ses", g.ses, "--ad", f"{sira} - {baslik}"])
        sonuc = "tamam" if r.returncode == 0 else f"hata{deneme}"
        with durum.open("a", encoding="utf-8") as f:
            f.write(f"{sira}\t{vid}\t{sonuc}\t{time.strftime('%m-%d %H:%M')}\t{(time.time() - t) / 60:.0f} dk\t{baslik}\n")
        print(f"[{sira}/{len(satirlar)}] {vid} {sonuc}", flush=True)
        if r.returncode == 0:
            break

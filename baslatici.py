"""Lokal Dublaj başlatıcısı: saatin yanındaki simge (tepsi). Açınca sunucuyu başlatır, durumunu gösterir, durdurur;
çeviri modelini seçtirir (deneme çevirisiyle); "Windows açılınca başlat" tercihi.
Çalıştır: .venv\\Scripts\\pythonw baslatici.py
"""
import json, os, subprocess, sys, threading, time, urllib.request, winreg

import ortak

A = ortak.ayar()
ADRES = f"http://127.0.0.1:{A['sunucu']['port']}"
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
AD = "LokalDublaj"


def istek(yol, yontem="GET"):
    r = urllib.request.Request(ADRES + yol, method=yontem, headers={"X-TR-Ses": "1"})
    with urllib.request.urlopen(r, timeout=2) as y:
        return json.load(y)


def durum():
    """(açık mı, kısa açıklama). Sorulan kimlik uydurma; yanıtın 'gpu_mesgul' alanı o an hazırlanan videoyu söyler."""
    try:
        b = istek("/bilgi/aaaaaaaaaaa")
    except Exception:
        return False, "Sunucu kapalı"
    g = b.get("gpu_mesgul")
    return True, f"Hazırlanıyor: {g['ad'][:40]} · {g['ilerleme'].split('·')[-1].strip()}" if g else "Sunucu açık"


def baslat(ayril=False):
    """ayril: Firefox köprüsünden çağrılınca sunucu Firefox'un süreç grubundan (Job) ayrılsın, köprü kapanınca ölmesin."""
    if durum()[0]:
        return
    A["calisma_klasoru"].mkdir(parents=True, exist_ok=True)
    gunluk = open(A["calisma_klasoru"] / "sunucu.log", "a", encoding="utf-8")
    # python.exe + gizli konsol (pythonw değil): yt-dlp/ffmpeg gibi alt programlar bu gizli konsolu devralır, pencere açmaz
    subprocess.Popen([str(ortak.KOK / ".venv" / "Scripts" / "python.exe"), str(ortak.KOK / "sunucu.py")],
                     cwd=ortak.KOK, stdin=subprocess.DEVNULL, stdout=gunluk, stderr=subprocess.STDOUT,
                     env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                     creationflags=subprocess.CREATE_NO_WINDOW | (subprocess.CREATE_BREAKAWAY_FROM_JOB if ayril else 0))
    for _ in range(20):  # açılması ~1 sn
        time.sleep(0.25)
        if durum()[0]:
            return


def durdur():
    try:
        istek("/kapat", "POST")
    except Exception:
        pass


def acilista():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            winreg.QueryValueEx(k, AD)
            return True
    except OSError:
        return False


def acilista_ayarla(evet):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN, 0, winreg.KEY_SET_VALUE) as k:
        if evet:
            pyw = ortak.KOK / ".venv" / "Scripts" / "pythonw.exe"
            winreg.SetValueEx(k, AD, 0, winreg.REG_SZ, f'"{pyw}" "{ortak.KOK / "baslatici.py"}"')
        else:
            try:
                winreg.DeleteValue(k, AD)
            except OSError:
                pass


def tepsi():
    import pystray
    from PIL import Image, ImageDraw

    def resim(acik):
        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((2, 2, 62, 62), 14, fill=(31, 95, 191) if acik else (90, 90, 90))
        d.text((14, 18), "TR", fill="white", font_size=30)
        return im

    son = {"metin": "", "acik": None, "modeller": None, "secili": "", "deneniyor": None}

    def metin(_):
        return son["metin"]

    def modelleri_yenile():
        a = ortak.ayar()
        try:
            son["modeller"] = ortak.model_listesi(a["ceviri"]["adres"])
        except ortak.Hata:
            son["modeller"] = None  # çeviri sunucusu kapalı
        son["secili"] = a["ceviri"]["model"]
        ikon.update_menu()

    def model_sec(kimlik):
        """Önce 3 cümlelik deneme çevirisi; ancak geçerse ayara yazılır. Sonuç bildirimle (çeviriler görünsün)."""
        son["deneniyor"] = kimlik
        ikon.update_menu()
        ikon.notify(f"{kimlik} deneniyor; model belleğe yükleniyorsa 1 dakikayı bulabilir.", "Lokal Dublaj · çeviri modeli")
        try:
            tr = ortak.deneme_cevirisi(ortak.ayar()["ceviri"]["adres"], kimlik)
            ortak.model_kaydet(kimlik)
            ikon.notify(f"Seçildi: {kimlik}. Yeni videolar bununla çevrilir.\n" + "\n".join(tr.values()), "Lokal Dublaj · çeviri modeli")
        except Exception as e:
            ikon.notify(f"{kimlik} seçilmedi: {e}", "Lokal Dublaj · çeviri modeli")
        son["deneniyor"] = None
        modelleri_yenile()

    def model_ogeleri():
        if son["modeller"] is None:
            yield pystray.MenuItem("Çeviri sunucusu kapalı (LM Studio'yu aç)", None, enabled=False)
        elif not son["modeller"]:
            yield pystray.MenuItem("Sunucuda sohbet modeli yok", None, enabled=False)
        for k, bellekte in son["modeller"] or []:
            ek = " · deneniyor…" if son["deneniyor"] == k else " · bellekte" if bellekte else ""
            yield pystray.MenuItem(k + ek, (lambda k: lambda: threading.Thread(target=model_sec, args=(k,)).start())(k),
                                   checked=(lambda k: lambda _: son["secili"] == k)(k), radio=True,
                                   enabled=not son["deneniyor"])
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Listeyi yenile", lambda: threading.Thread(target=modelleri_yenile).start())

    menu = pystray.Menu(
        pystray.MenuItem(metin, None, enabled=False),
        pystray.MenuItem(lambda _: "Durdur" if son["acik"] else "Başlat",
                         lambda: threading.Thread(target=durdur if son["acik"] else baslat).start(), default=True),
        pystray.MenuItem(lambda _: f"Çeviri modeli: {son['secili'] or 'seçilmedi'}", pystray.Menu(model_ogeleri)),
        pystray.MenuItem("Windows açılınca başlat", lambda: acilista_ayarla(not acilista()), checked=lambda _: acilista()),
        pystray.MenuItem("Çıkış (sunucuyu da kapatır)", lambda i: (durdur(), i.stop())),
    )
    ikon = pystray.Icon(AD, resim(False), "Lokal Dublaj", menu)

    def izle():
        baslat()
        tur = 0
        while True:
            if tur % 10 == 0 and not son["deneniyor"]:  # model listesi ~30 sn'de bir (LM Studio sonradan açılabilir)
                modelleri_yenile()
            tur += 1
            acik, m = durum()
            if (acik, m) != (son["acik"], son["metin"]):
                son.update(acik=acik, metin=m)
                ikon.icon, ikon.title = resim(acik), f"Lokal Dublaj · {m}"
                ikon.update_menu()
            time.sleep(3)

    ikon.run(setup=lambda i: (setattr(i, "visible", True), threading.Thread(target=izle, daemon=True).start()))


if __name__ == "__main__":
    kilit = open(ortak.KOK / ".baslatici-kilit", "a+")
    if not ortak.kilit_dene(kilit):  # başlatıcı zaten açık: ikinci kopya açılmaz
        sys.exit(0)
    tepsi()

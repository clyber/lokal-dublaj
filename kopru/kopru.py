"""Firefox köprüsü (native messaging): eklenti, sunucu kapalıyken videodaki düğmeye basılınca buna {"komut": "baslat"} yollar.
Köprü tepsi simgesini açar (o da sunucuyu başlatır); simge zaten açık ama sunucu durdurulmuşsa sunucuyu doğrudan başlatır.
Firefox bunu kopru.bat üzerinden çalıştırır; kayıt: kopru-kur.ps1. Mesaj biçimi: 4 bayt uzunluk + JSON (stdin/stdout).
"""
import json, struct, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import baslatici as b
import ortak


def oku():
    n = sys.stdin.buffer.read(4)
    return json.loads(sys.stdin.buffer.read(struct.unpack("<I", n)[0])) if len(n) == 4 else None


def yaz(v):
    d = json.dumps(v).encode()
    sys.stdout.buffer.write(struct.pack("<I", len(d)) + d)
    sys.stdout.buffer.flush()


def tepsi_acik():
    with open(ortak.KOK / ".baslatici-kilit", "a+") as f:
        if ortak.kilit_dene(f):
            ortak.kilit_birak(f)
            return False
    return True


def ac():
    if b.durum()[0]:
        return True
    if not tepsi_acik():
        # Firefox köprüyü bir Job içinde çalıştırır; ayrılmazsa köprü kapanınca simge de kapanır
        subprocess.Popen([str(ortak.KOK / ".venv" / "Scripts" / "pythonw.exe"), str(ortak.KOK / "baslatici.py")],
                         cwd=ortak.KOK, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                         | subprocess.CREATE_BREAKAWAY_FROM_JOB)
        for _ in range(40):  # simge açılıp sunucuyu başlatana kadar (~2 sn)
            time.sleep(0.25)
            if b.durum()[0]:
                return True
    b.baslat(ayril=True)  # simge açık ama sunucu durdurulmuş
    return b.durum()[0]


if __name__ == "__main__":
    m = oku()
    yaz({"acik": ac()} if m and m.get("komut") == "baslat" else {"hata": "bilinmeyen komut"})

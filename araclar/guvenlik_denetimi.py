"""Sunucu güvenliğinin öz denetimi (G01): belirteçsiz, yanlış belirteçli, yabancı Host'lu ve biletsiz istekler reddedilmeli;
doğru belirteç ve bilet çalışmalı. Sunucu açık olmalı (simge ya da sunucu-baslat.bat). Çalıştır: python araclar/guvenlik_denetimi.py"""
import http.client, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ortak

PORT = ortak.ayar()["sunucu"]["port"]
B = ortak.belirtec()


def istek(yol, yontem="GET", baslik=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
    c.request(yontem, yol, headers=baslik or {})
    r = c.getresponse()
    return r.status, r.read()


# bir video seç: hazır olan varsa onu (ses denemesi için)
is_kok = ortak.ayar()["calisma_klasoru"]
hazir = next((d.name for d in is_kok.iterdir() if d.is_dir() and any(d.glob("bitti-*"))), "aaaaaaaaaaa")
dogru = {"X-TR-Belirtec": B}

assert istek(f"/durum/{hazir}")[0] == 401, "belirteçsiz durum okundu"
assert istek(f"/durum/{hazir}", baslik={"X-TR-Belirtec": "yanlis"})[0] == 401, "yanlış belirteç kabul edildi"
assert istek(f"/durum/{hazir}", baslik={**dogru, "Host": "kotu.example:8799"})[0] == 401, "yabancı Host kabul edildi"
assert istek("/hazirla/aaaaaaaaaaa", "POST")[0] == 401, "belirteçsiz iş başlatılabildi"
assert istek("/kapat", "POST", {"X-TR-Ses": "1"})[0] == 401, "eski sabit başlıkla sunucu kapatılabildi"
print("tamam: belirteçsiz / yanlış belirteçli / yabancı Host'lu / eski başlıklı istekler reddedildi")

s, g = istek(f"/durum/{hazir}", baslik=dogru)
assert s == 200, s
d = json.loads(g)
print("tamam: doğru belirteçle durum ->", d.get("durum"))
if d.get("durum") == "hazir":
    assert istek(f"/ses/{hazir}.m4a")[0] == 401, "biletsiz ses okundu"
    assert istek(f"/ses/{hazir}.m4a?b={B}")[0] == 401, "ana belirteç bilet yerine geçti"
    assert istek(f"/ses/{hazir}.m4a?b={d['bilet']}", baslik={"Range": "bytes=0-99"})[0] == 206, "doğru biletle ses okunamadı"
    baska = next((x.name for x in is_kok.iterdir() if x.is_dir() and x.name != hazir and any(x.glob("bitti-*"))), None)
    if baska:
        assert istek(f"/ses/{baska}.m4a?b={d['bilet']}")[0] == 401, "bir videonun bileti başka videoyu açtı"
    print("tamam: ses yalnız o videoya özel biletle açılıyor")

# Güvenlik

Bir güvenlik açığı bulduysan **herkese açık issue açma**. GitHub'da depo sayfasındaki **Security → Report a vulnerability** ile özel olarak bildir. Bildirimde ne yaptığını, ne beklediğini ve ne olduğunu, Lokal Dublaj sürümünü yaz; belirteç (`.belirtec`), ayar dosyanın tamamı ya da izleme geçmişin gerekmez.

## Kapsam ve tasarım

- Sunucu yalnız `127.0.0.1:8799`'da dinler; dışarıdan erişilemez.
- Her istek kurulum başına üretilen gizli belirteci ister (`.belirtec`, git dışı). Firefox eklentisi onu yalnız native messaging köprüsünden alır; Firefox o kanalı yalnız bu eklentinin kimliğine açar. Ses adresi yalnız o videoya özel biletle açılır, `Host` 127.0.0.1/localhost değilse istek reddedilir.
- Aynı Windows hesabında çalışan ve dosyalarını okuyabilen bir programa karşı koruma iddiası yoktur; o program zaten kullanıcının yetkisine sahiptir.
- Denetim: `python araclar/guvenlik_denetimi.py` (sunucu açıkken).

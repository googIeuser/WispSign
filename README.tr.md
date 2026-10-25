# WispSign

[English](README.md)

WispSign, iOS uygulamalarını (`.ipa`) kendi sertifikanla yeniden imzalayan ve USB ile
iPhone'a yükleyen bir Windows masaüstü uygulamasıdır. İmzalama
[zsign](https://github.com/zhlynn/zsign), yükleme
[pymobiledevice3](https://github.com/doronz88/pymobiledevice3) ile yapılır. Her şey yerelde
çalışır: sertifikaların bilgisayarından çıkmaz, parolalar Windows DPAPI ile şifreli saklanır.

![Kütüphane: imzala ve yükle](docs/screenshots/library.png)

## Gereksinimler

- Windows 10 veya 11 (x64)
- **Apple Devices** (Microsoft Store) veya iTunes; Windows'ta Apple USB sürücüsü için
- Microsoft Edge WebView2 çalışma zamanı (güncel Windows 10/11'de hazır gelir)
- Bir Apple imzalama sertifikası: `.p12` dosyası, parolası ve eşleşen `.mobileprovision`
  profili
- USB ile bağlı, kilidi açık, "Bu bilgisayara güven" onaylanmış bir iPhone

## Kurulum

Projenin GitHub Releases sayfasından
`WispSign-Setup-<sürüm>.exe` dosyasını indirip çalıştır. Taşınabilir bir `.zip` de
yayınlanır; arşivi aç ve `WispSign.exe`'yi başlat.

> Kurulum dosyası ve `WispSign.exe` kod imzalı değildir, bu yüzden Windows SmartScreen
> uyarı gösterebilir. "Ek bilgi"ye ve ardından "Yine de çalıştır"a tıkla.

## Hızlı başlangıç

1. **Sertifika ekle** (Sertifikalar): bir ad ve `.p12` şifresini gir, sonra "Dosyaları seç"e
   bas; önce `.p12`, ardından `.mobileprovision` dosyasını seç. WispSign kalan günü,
   profilin iPhone'unu kapsayıp kapsamadığını ve bildirim (push) yetkisi olup olmadığını
   gösterir.
2. **IPA ekle** (Kütüphane): "IPA ekle"ye tıkla veya `.ipa` dosyalarını pencereye sürükle.
   Kendi eklediğin bir repodan da uygulama eklenebilir (Repolar).
3. **İmzala ve yükle**: uygulamayı seç, sertifikayı seç ve "İmzala ve Yükle"ye bas.
   Bundle ID, görünen ad ve simge "Gelişmiş seçenekler" altındadır; varsayılan olarak
   özgün bundle ID korunur. İlerleme canlı gösterilir; bitince uygulama bağlı iPhone'da
   görünür.

| Sertifikalar | Cihaz | Repolar |
| --- | --- | --- |
| ![Sertifikalar](docs/screenshots/certs.png) | ![Cihaz](docs/screenshots/device.png) | ![Repolar](docs/screenshots/repos.png) |

Ekran görüntüleri örnek verilerle Türkçe arayüzü gösterir.

## Bildirimler (push)

Bildirimler yalnızca uygulama özgün bundle ID'siyle ve **Push Notifications yetkisi olan
açık (explicit) bir App ID** profiliyle imzalandığında çalışır (joker `*` profil olmaz).
"Gelişmiş seçenekler" altındaki bundle ID ayarını "Koru" (varsayılan) bırak ve profilinde push açık olan bir sertifika seç;
Sertifikalar sayfası push yetkisi olmayan profilleri işaretler.

İmzalama öncesinde süresi dolmuş, cihazı kapsamayan veya uygulama kimliği uyuşmayan
profiller reddedilir. İmzalama sonrasında uygulamanın kimlik ve bildirim yetkileri de
profille karşılaştırılır. Bu kontrol, bildirimin telefona ulaştığını kanıtlamaz;
[gerçek cihaz testi](docs/device-test.md) ayrıca yapılmalıdır.

## Sınırlar

- Yalnızca Windows 10/11 x64; yalnızca USB ile iPhone (Wi-Fi ile yükleme yok).
- Sertifikanın bir bitiş tarihi vardır; sertifika veya profil bitince uygulama açılmaz ve
  yeniden imzalanmalıdır.
- Profilde iPhone'unun UDID'si bulunmalı ya da profil açıkça tüm cihazlara izin vermelidir.
- Joker profiller push bildirimleri ve bazı yetkiler için yeterli değildir.
- Repo verisi güvenilmez kabul edilir: yalnızca `https://` adresleri, en fazla 5 MB repo
  JSON'u, en fazla 4 GB IPA indirmesi, 20 sn zaman aşımı. Mutlak veya `..` yollu, sembolik bağlantı içeren ya da açılmış
  hali 4 GB'ı aşan IPA'lar reddedilir.
- **Uygulamayla birlikte hiçbir repo gelmez.** Repo adreslerini kendin eklersin; imzaladığın
  ve yüklediğin uygulamalardan sen sorumlusun.

Parolanın nasıl korunduğu ve yerel profil/imza kontrollerinin sınırları için
[güvenlik sınırları](docs/security.md) belgesine bak (İngilizce).

## Kaynaktan derleme

Python 3.12, Node.js 22 ve PowerShell gerekir.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -c requirements-lock.txt -e ".[dev]"
packaging\build.ps1
```

Betik zsign'ı indirir (sabitlenmiş SHA-256), arayüzü derler, PyInstaller'ı çalıştırır ve
Inno Setup (`iscc`) kuruluysa yükleyiciyi üretir. Çıktı: `dist\WispSign\WispSign.exe` ve
`dist\WispSign-Setup-<sürüm>.exe`.

Uygulamaya kişisel bir yayın hesabı gömülmez. Güncelleme kontrolü için çalıştırma
ortamında `WISPSIGN_UPDATE_REPO` değişkeni, herkese açık projenin `sahip/depo` adresine
ayarlanmalıdır. Ayarlanmamışsa Ayarlar sayfasında güncelleme kontrolü görünmez.

### Geliştirme

Yukarıdaki gibi kur (`-c requirements-lock.txt`, yayın derlemesiyle aynı bağımlılık
sürümlerini kullanır), ardından kontrolleri çalıştır:

```powershell
.venv\Scripts\python packaging\fetch_zsign.py
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check src tests packaging
cd ui; npm ci; npm run lint; npm run check; npm test; npx playwright test
```

## Lisans

GPL-3.0-or-later, bkz. [LICENSE](LICENSE). Pakete dahil zsign ikilisi kendi lisansını
[third_party/zsign/LICENSE](third_party/zsign/LICENSE) altında korur.

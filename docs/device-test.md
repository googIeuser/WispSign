# WispSign: gerçek iPhone testi

Durum: bu sürümde bildirimler (push) gerçek bir iPhone'da test edildi ve çalışıyor
(2026-10-25). Simge değiştirme henüz gerçek cihazda doğrulanmadı.

Otomatik testler imzalı IPA'daki ana uygulamanın XML kimlik ve bildirim yetkilerini
denetler. Apple'ın cihazdaki imza/profil doğrulaması ve bildirimin teslim edilmesi
bu testlerin kapsamına girmez.

Testte kullanılacak IPA ve sertifika/profil çifti kullanıcı tarafından seçilir.
Profil geçerli olmalı, test iPhone'unu kapsamalı ve bildirim testi için uygulamanın
özgün bundle ID'siyle eşleşen açık App ID üzerinde push yetkisi içermelidir.

1. Paketlenmiş `dist\WispSign\WispSign.exe` dosyasını aç. Windows ve iOS sürümünü,
   WispSign sürümünü ve test IPA'sının sürümünü sonuç kaydına yaz.
2. iPhone'u USB ile bağla, kilidini aç ve gerekiyorsa bilgisayara güven. Cihaz
   ekranında telefonun ve yüklü uygulamaların göründüğünü doğrula.
3. Seçilen sertifika/profil çiftini ekle. Süre ve cihaz bilgilerinin doğru olduğunu
   doğrula. Süresi dolmuş, başka cihazı kapsayan veya başka uygulamaya ait profil
   seçildiğinde imzalama düğmesinin kapalı kaldığını kontrol et.
4. Deneme IPA'sını ekle; bundle ID'yi koruyarak imzala ve yükle. Doğrulama ve yükleme
   adımlarının tamamlandığını, uygulamanın telefonda açıldığını kontrol et.
5. Uygulamada bildirim iznini ver ve bilinen bir olayla bildirim gönderilmesini
   tetikle. Uygulama arka plandayken ve telefon kilitliyken bildirimin gerçekten
   geldiğini kaydet. Sadece arayüzdeki push etiketi başarı ölçütü değildir.
6. Aynı deneme uygulamasını aynı sertifika ve bundle ID ile güncelle. Uygulamanın
   açıldığını, test verilerinin korunduğunu ve yeni bildirimin geldiğini doğrula.
7. Test için ayrılmış uygulamayı Cihaz ekranından kaldır ve listeden silindiğini
   doğrula.

Her adım için gerçek sonucu ve varsa hatanın kodunu kaydet. Parola, özel anahtar,
sertifika dosyası veya tam cihaz UDID'sini sonuç kaydına ekleme.

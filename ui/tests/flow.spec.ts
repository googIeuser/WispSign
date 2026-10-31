import { expect, test } from '@playwright/test'

test('demo screenshots clearly identify their fictional device data', async ({ page }) => {
  await page.goto('/?mock')
  await expect(page.getByText('Örnek veriler', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Sertifikalar' }).click()
  await page.getByText('Yedek (pushsuz)').click()
  const detail = page.locator('#detail')
  await expect(detail.getByText('DEMO-OTHER-DEVICE', { exact: true })).toBeVisible()
  expect(await detail.innerText()).not.toMatch(/\b[0-9a-f]{8}-[0-9a-f]{16}\b|\b[0-9a-f]{40}\b/i)
})

test('add repo → download → sign & install shows all steps', async ({ page }) => {
  await page.goto('/?mock')
  await page.getByRole('button', { name: 'Repolar' }).click()
  await page.getByRole('button', { name: 'Repo ekle' }).click()
  await page.getByRole('textbox').fill('https://example.com/repo.json')
  await page.getByRole('button', { name: 'Ekle' }).click()
  await page.getByText('Demo App').click()
  await page.getByRole('button', { name: 'İndir ve Kütüphaneye Ekle' }).click()
  await expect(page.locator('#detail').getByText('Kütüphaneye eklendi')).toBeVisible()
  await page.getByRole('button', { name: 'Kütüphane' }).click()
  await page.getByText('Demo App').click()
  await page.getByRole('button', { name: 'İmzala ve Yükle' }).click()
  for (const step of ['Paket açılıyor', 'İmzalanıyor', 'Doğrulanıyor', 'Paketleniyor']) {
    await expect(page.getByRole('status').getByText(step)).toBeVisible()
  }
  await expect(page.getByTestId('job-done')).toBeVisible()
})

test('repo description with HTML is shown as text', async ({ page }) => {
  await page.goto('/?mock&htmldesc')
  await page.getByText('Demo App').click()
  const detail = page.locator('#detail')
  await expect(detail.getByText('<b>x</b>', { exact: true })).toBeVisible()
  await expect(detail.locator('b')).toHaveCount(0)
})

test('mapped error shows friendly text with detail toggle', async ({ page }) => {
  await page.goto('/?mock&failsign&seedlib')
  await page.getByRole('button', { name: 'Kütüphane' }).click()
  await page.getByText('Demo App').click()
  await page.getByRole('button', { name: 'İmzala ve Yükle' }).click()
  const alert = page.getByRole('alert')
  await expect(alert.getByText('Uygulama telefonda farklı bir sertifikayla yüklü', { exact: false })).toBeVisible()
  const detail = alert.getByText('mock', { exact: true })
  await expect(detail).toBeHidden()
  await alert.getByText('Ayrıntılar').click()
  await expect(detail).toBeVisible()
  await expect(page.getByTestId('job-done')).toHaveCount(0)
})

test('sign button disabled without device', async ({ page }) => {
  await page.goto('/?mock&nodevice&seedlib')
  await page.getByRole('button', { name: 'Kütüphane' }).click()
  await page.getByText('Demo App').click()
  await expect(page.getByRole('button', { name: 'İmzala ve Yükle' })).toBeDisabled()
})

test('sign panel blocks a certificate that does not cover the device', async ({ page }) => {
  await page.goto('/?mock&seedlib')
  await page.getByRole('button', { name: 'Kütüphane' }).click()
  await page.getByText('Demo App').click()
  const detail = page.locator('#detail')
  await expect(detail.getByText('bildirim (push) yetkisi yok')).toHaveCount(0)
  await detail.getByRole('combobox', { name: 'Sertifika' }).selectOption({ label: 'Yedek (pushsuz)' })
  await expect(detail.getByText('bildirim (push) yetkisi yok')).toBeVisible()
  await expect(detail.getByText('cihaz sertifika profilinde kayıtlı değil')).toBeVisible()
  await expect(page.getByRole('button', { name: 'İmzala ve Yükle' })).toBeDisabled()
})

test('sign panel warns when an explicit App ID does not match the bundle ID', async ({ page }) => {
  await page.goto('/?mock&seedlib')
  await page.getByRole('button', { name: 'Kütüphane' }).click()
  await page.getByText('Demo App').click()
  const detail = page.locator('#detail')
  await expect(page.getByRole('button', { name: 'İmzala ve Yükle' })).toBeEnabled()
  await expect(detail.getByText('uygulama kimliği', { exact: false })).toHaveCount(0)
  await detail.getByRole('button', { name: 'Gelişmiş seçenekler' }).click()
  await detail.getByText('Değiştir', { exact: true }).click()
  await detail.getByRole('textbox', { name: 'Yeni bundle ID' }).fill('com.example.other')
  await expect(detail.getByText('(com.example.other) uyuşmuyor', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'İmzala ve Yükle' })).toBeDisabled()
})

test('advanced sign options open and close with the keyboard', async ({ page }) => {
  await page.goto('/?mock&seedlib')
  await page.getByRole('button', { name: 'Kütüphane' }).click()
  await page.getByText('Demo App').click()
  const detail = page.locator('#detail')
  const toggle = detail.getByRole('button', { name: 'Gelişmiş seçenekler' })
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(detail.getByRole('button', { name: 'PNG seç' })).toHaveCount(0)
  await toggle.focus()
  await page.keyboard.press('Enter')
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(detail.getByRole('button', { name: 'PNG seç' })).toBeVisible()
  await page.keyboard.press('Space')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
})

test('device screen shows help when no device is connected', async ({ page }) => {
  await page.goto('/?mock&nodevice')
  await page.getByRole('button', { name: 'Cihaz' }).click()
  await expect(page.getByRole('heading', { name: 'iPhone görünmüyor' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Apple Devices kurulu mu?' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Tekrar dene' })).toBeVisible()
})

test('device screen lists installed apps', async ({ page }) => {
  await page.goto('/?mock')
  await page.getByRole('button', { name: 'Cihaz' }).click()
  await page.getByText('Demo App').click()
  await expect(page.locator('#detail').getByRole('heading', { name: 'Demo App' })).toBeVisible()
  await expect(page.locator('#detail').getByText('com.example.demo').first()).toBeVisible()
})

test('certificates show cards with push status', async ({ page }) => {
  await page.goto('/?mock')
  await page.getByRole('button', { name: 'Sertifikalar' }).click()
  await expect(page.getByText('Ana sertifika')).toBeVisible()
  await expect(page.getByText('Yedek (pushsuz)')).toBeVisible()
  await page.getByText('Yedek (pushsuz)').click()

  await expect(page.getByRole('option', { name: /Yedek/ }).getByText('3 gün kaldı')).toBeVisible()
  await expect(page.locator('#detail').getByText('3 gün içinde sona erecek', { exact: false })).toBeVisible()

  const enterprise = page.getByRole('option', { name: /Kurumsal/ })
  await expect(enterprise.getByText('tüm cihazlar')).toBeVisible()
  await expect(enterprise.getByText('bu iPhone kayıtlı', { exact: true })).toBeVisible()
})

test('a broken certificate is marked and can be removed', async ({ page }) => {
  await page.goto('/?mock&brokencert')
  await page.getByRole('button', { name: 'Sertifikalar' }).click()
  const broken = page.getByRole('option', { name: /9f8e7d6c5b4a/ })
  await expect(broken.getByText('bozuk', { exact: true })).toBeVisible()
  await broken.click()
  const detail = page.locator('#detail')
  await expect(detail.getByRole('alert')).toContainText('kaydı okunamıyor')
  await detail.getByRole('button', { name: 'Kaldır' }).click()
  await detail.getByRole('button', { name: 'Kaldır' }).click()
  await expect(page.getByRole('option', { name: /9f8e7d6c5b4a/ })).toHaveCount(0)
})

test('settings switch language and validate the download folder', async ({ page }) => {
  await page.goto('/?mock')
  await page.getByRole('button', { name: 'Ayarlar' }).click()
  const folder = page.getByRole('textbox', { name: 'İndirme klasörü' })
  await folder.fill('relative\\path')
  await page.getByRole('button', { name: 'Kaydet' }).click()
  await expect(page.getByText('tam bir klasör yolu', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'English' }).click()
  await expect(page.getByRole('button', { name: 'Library' })).toBeVisible()
})

test('the folder picker fills the download folder, saving still validates', async ({ page }) => {
  await page.goto('/?mock')
  await page.getByRole('button', { name: 'Ayarlar' }).click()
  await page.getByRole('button', { name: 'Klasör seç' }).click()
  const folder = page.getByRole('textbox', { name: 'İndirme klasörü' })
  await expect(folder).toHaveValue(/^D:.IPA$/)
  await page.getByRole('button', { name: 'Kaydet' }).click()
  await expect(page.getByText('Ayar kaydedildi.')).toBeVisible()
})

test('app list is keyboard operable', async ({ page }) => {
  await page.goto('/?mock')
  const options = page.getByRole('listbox', { name: 'Repo uygulamaları' }).getByRole('option')
  await expect(options).toHaveCount(2)
  await options.first().focus()
  await page.keyboard.press('Enter')
  await expect(options.first()).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('ArrowDown')
  await expect(options.nth(1)).toHaveAttribute('aria-selected', 'true')
  await expect(options.nth(1)).toBeFocused()
  await expect(page.locator('#detail').getByRole('heading', { name: 'Sample Tool' })).toBeVisible()
})

test('removing a downloaded IPA lets the repo app be downloaded again', async ({ page }) => {
  await page.goto('/?mock')
  await page.getByText('Demo App').click()
  await page.getByRole('button', { name: 'İndir ve Kütüphaneye Ekle' }).click()
  await expect(page.locator('#detail').getByText('Kütüphaneye eklendi')).toBeVisible()
  await page.getByRole('button', { name: 'Kütüphane', exact: true }).click()
  await page.getByText('Demo App').click()
  await page.locator('#detail').getByRole('button', { name: 'Kaldır' }).click()
  await page.locator('#detail').getByRole('button', { name: 'Kaldır' }).click()
  await expect(page.getByText('Kütüphane boş')).toBeVisible()
  await page.getByRole('button', { name: 'Repolar' }).click()
  await page.getByText('Demo App').click()
  await expect(page.getByRole('button', { name: 'İndir ve Kütüphaneye Ekle' })).toBeVisible()
  await expect(page.locator('#detail').getByText('Kütüphaneye eklendi')).toHaveCount(0)
})

test('failing certificate validation shows an error instead of no warnings', async ({ page }) => {
  await page.goto('/?mock&failvalidate&seedlib')
  await page.getByRole('button', { name: 'Kütüphane', exact: true }).click()
  await page.getByText('Demo App').click()
  await expect(page.locator('#detail').getByRole('alert')).toContainText('Sertifika kaydı bozulmuş')
  await page.getByRole('button', { name: 'Sertifikalar' }).click()
  await page.getByText('Ana sertifika').click()
  await expect(page.locator('#detail').getByRole('alert')).toContainText('Sertifika kaydı bozulmuş')
})

async function importCert(page: import('@playwright/test').Page) {
  await page.getByRole('button', { name: 'Sertifikalar' }).click()
  await page.getByRole('button', { name: 'Sertifika ekle' }).click()
  await page.getByRole('textbox', { name: 'Sertifika adı' }).fill('Yeni')
  await page.getByRole('button', { name: 'Dosyaları seç' }).click()
  await expect(page.getByText('Yeni eklendi')).toBeVisible()
}

test('wizard does not claim the device is registered when none is connected', async ({ page }) => {
  await page.goto('/?mock&nodevice')
  await importCert(page)
  await expect(page.getByText('Bağlı cihaz yok, cihaz kaydı denetlenmedi.')).toBeVisible()
  await expect(page.getByText('Sertifika ve profil uyumlu', { exact: false })).toHaveCount(0)
})

test('wizard shows a failed validation as an error', async ({ page }) => {
  await page.goto('/?mock&failvalidate')
  await importCert(page)
  await expect(page.locator('#detail').getByRole('alert')).toContainText('Sertifika kaydı bozulmuş')
  await expect(page.getByText('Sertifika ve profil uyumlu', { exact: false })).toHaveCount(0)
})

test('wizard reports success when validation passes with a device', async ({ page }) => {
  await page.goto('/?mock')
  await importCert(page)
  await expect(page.getByText('Sertifika ve profil uyumlu', { exact: false })).toBeVisible()
})

test('a failed update check is not reported as up to date', async ({ page }) => {
  await page.goto('/?mock&updatefail')
  await page.getByRole('button', { name: 'Ayarlar' }).click()
  await page.getByRole('button', { name: 'Güncellemeleri denetle' }).click()
  await expect(page.getByText('Güncelleme kontrol edilemedi', { exact: false })).toBeVisible()
  await expect(page.getByText('Güncel sürümü kullanıyorsun')).toHaveCount(0)
})

test('an up-to-date check says so', async ({ page }) => {
  await page.goto('/?mock')
  await page.getByRole('button', { name: 'Ayarlar' }).click()
  await page.getByRole('button', { name: 'Güncellemeleri denetle' }).click()
  await expect(page.getByText('Güncel sürümü kullanıyorsun', { exact: false })).toBeVisible()
})

test('without a configured release repo there is no update check', async ({ page }) => {
  await page.goto('/?mock&noupdates')
  await page.getByRole('button', { name: 'Ayarlar' }).click()
  await expect(page.getByText('v0.1.0')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Güncellemeleri denetle' })).toHaveCount(0)
})

test('settings clears the cache after confirmation', async ({ page }) => {
  await page.goto('/?mock')
  await page.getByRole('button', { name: 'Ayarlar' }).click()
  await page.getByRole('button', { name: 'Önbelleği temizle' }).click()
  await expect(page.getByText('Önbellek silinsin mi?', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Temizle', exact: true }).click()
  await expect(page.getByText('46.0 MB boşaltıldı.')).toBeVisible()
})

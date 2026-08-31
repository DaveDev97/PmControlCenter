# Code Signing (Windows)

Gli eseguibili non firmati vengono bloccati da SmartScreen / Smart App Control /
policy aziendali. Il workflow di release è **già predisposto** per firmare
automaticamente: appena aggiungi i secret del certificato, la prossima release
(`v1.0.x`) esce firmata. Senza secret, la build resta non firmata (nessun errore).

Il meccanismo è in [`.github/workflows/release.yml`](.github/workflows/release.yml):
electron-builder firma automaticamente se trova `CSC_LINK` + `CSC_KEY_PASSWORD`.

---

## Opzione A — Certificato OV con file `.pfx` (classica)

Adatta se il tuo certificato di code signing è esportabile in un file
`.pfx` / `.p12` con password.

1. **Procurati un certificato OV** da una CA (Sectigo, DigiCert, GlobalSign…).
   > Nota: dal 2023 molte CA rilasciano gli OV solo su token hardware/HSM; in
   > quel caso il file `.pfx` non è disponibile → usa l'Opzione B.
2. **Codifica il .pfx in base64**:
   - Linux/macOS: `base64 -w0 certificato.pfx > cert.b64`
   - Windows PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("certificato.pfx")) > cert.b64`
3. **Aggiungi i secret** nel repo GitHub → *Settings → Secrets and variables → Actions → New repository secret*:
   - `WINDOWS_CSC_LINK` = contenuto di `cert.b64` (la stringa base64)
   - `WINDOWS_CSC_KEY_PASSWORD` = password del `.pfx`
4. **Rilascia**: `git tag v1.0.4 && git push origin v1.0.4` → l'installer e il
   portable escono firmati.

---

## Opzione B — Azure Trusted Signing (consigliata, moderna)

Servizio Microsoft (~10 $/mese), niente file di chiavi, e costruisce
reputazione SmartScreen rapidamente. Richiede un account Azure e un
"Trusted Signing account + Certificate profile".

1. Aggiungi a `package.json` sotto `build.win`:
   ```json
   "azureSignOptions": {
     "publisherName": "La Tua Azienda S.p.A.",
     "endpoint": "https://<region>.codesigning.azure.net/",
     "certificateProfileName": "<profilo>",
     "codeSigningAccountName": "<account>"
   }
   ```
2. Aggiungi al passo *Build & publish* del workflow gli env:
   ```yaml
   AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
   AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
   AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
   ```
3. Crea i tre secret corrispondenti (service principal Azure con ruolo
   *Trusted Signing Certificate Profile Signer*).

---

## Note sulla reputazione SmartScreen

- **OV**: la firma elimina l'errore "editore sconosciuto", ma SmartScreen può
  ancora avvisare finché il certificato non accumula reputazione (qualche
  download/tempo).
- **EV** o **Azure Trusted Signing**: reputazione (quasi) immediata.
- Su PC **gestiti dall'IT**, anche un'app firmata può richiedere la
  **whitelist** aziendale (AppLocker/WDAC): in quel caso coordina con l'IT
  fornendo il publisher/thumbprint del certificato.

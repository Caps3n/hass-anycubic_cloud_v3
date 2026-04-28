# Anycubic HA Integration

> 🗓️ **Fork von [@Caps3n](https://github.com/Caps3n) – April 2026**  
> Basiert auf dem Fork von [@ljschmitt](https://github.com/ljschmitt/hass-anycubic_cloud_v3), der wiederum auf [@WaresWichall](https://github.com/WaresWichall/hass-anycubic_cloud) aufbaut.  
> Aktuell getestet mit **Kobra X** – Feedback willkommen!

> 🗓️ **Ursprüngliches Update (11.10.2025):**  
> Diese Version enthält die **integrierte `paho-mqtt` 2.x-Lösung** (Callback-API v1) – damit funktionieren **MQTT-Echtzeit-Updates** wieder.  
> Voraussetzung: **Slicer Next (Windows)** und dessen **Access-Token** (einmalig auslesen, danach kein Windows nötig).  
> Kein harter Pin mehr auf `paho-mqtt==1.6.1`.

➡️ Dieser Fork enthält zusätzlich:
- Fehlerkorrekturen
- deutsche Texte
- MQTT-Erweiterungen
- verbesserter MQTT-Fallback bei Verbindungsproblemen
- GitHub Actions auf v4 aktualisiert
- HA 2025.11+ Kompatibilität

---

## 📚 Inhalt

- [🧵 Kompatible Drucker](#-kompatible-drucker)
- [⚙️ Funktionsweise](#-funktionsweise)
- [🎨 Frontend-Card](#-frontend-card)
- [🖼️ Galerie](#-galerie)
- [🧩 Features](#-features)
- [📦 Installation über HACS (empfohlen)](#-installation-über-hacs-empfohlen)
- [🖐️ Manuelle Installation](#-manuelle-installation)
- [🔐 Token auslesen (Slicer Next)](#-token-auslesen-slicer-next)
- [🌐 Web-Login (ohne MQTT, nur Polling)](#-web-login-ohne-mqtt-nur-polling)
- [📥 Releases](#-releases)
- [🙌 Mitwirkende](#-mitwirkende)
- [📄 Lizenz](#-lizenz)
- [💬 Feedback / Probleme](#-feedback--probleme)
- [✅ Kompatibilität](#-kompatibilität)

---

## 🧵 Kompatible Drucker

Die Komponente funktioniert getestet mit:
- ✅ Kobra 3 Combo
- ✅ Kobra 2, 2 Max, 2 Pro
- ✅ Photon Mono M5s (Basis)
- ✅ Anycubic M7 Pro (Basis)
- 🧪 Kobra X (in Testphase, Basis-Funktionen funktionieren)

Du hast andere Modelle? Bitte Rückmeldung geben 🙏

---

## ⚙️ Funktionsweise

- Cloud-Polling: alle **1 Minute**
- MQTT (Echtzeit): **mehrfach pro Sekunde**
- Erfordert **Slicer Next Token** für MQTT-Zugriff

---

## 🎨 Frontend-Card

Die Lovelace-Karte (`anycubic-printercard`) ist **direkt in dieser Integration enthalten** und wird beim HA-Start automatisch als Ressource registriert.

> ⚠️ **`WaresWichall/hass-anycubic_card` NICHT separat installieren!**  
> Das separate HACS-Plugin wird nicht mehr benötigt und kann zu Konflikten führen.  
> Falls es noch installiert ist: in HACS entfernen → HA neu starten → Browser-Cache leeren (`Cmd+Shift+R`).

Falls die automatische Registrierung nicht funktioniert, manuell hinzufügen unter **Einstellungen → Dashboards → Ressourcen**:
- **URL:** `/anycubic-card-static`
- **Typ:** `JavaScript-Modul`

---

## 🖼️ Galerie

<img width="300" src="https://raw.githubusercontent.com/WaresWichall/hass-anycubic_cloud/master/screenshots/kobra3-1.png">  
<img width="300" src="https://raw.githubusercontent.com/WaresWichall/hass-anycubic_cloud/master/screenshots/anycubic-ace-ui.gif">  
<img width="300" src="https://raw.githubusercontent.com/WaresWichall/hass-anycubic_cloud/master/screenshots/kobra2-2.png">  
<img width="300" src="https://raw.githubusercontent.com/WaresWichall/hass-anycubic_cloud/master/screenshots/kobra3-print.png">  
<img width="200" src="https://raw.githubusercontent.com/WaresWichall/hass-anycubic_cloud/master/screenshots/kobra2-1.png">

---

## 🧩 Features

- Mehrere Drucker gleichzeitig
- Druckstart / Pause / Fortsetzen / Abbruch (via Services & UI)
- ACE-Slot-Verwaltung (Farbe, Presets, Services)
- Dateimanager (MQTT benötigt)
- Sensoren: Temp, Speed, Fan, Job-Fortschritt, Name, Zeit, …
- Firmware-Update-Entitäten
- MQTT-Aktivität automatisch während Druck (oder dauerhaft)
- Frontend-Panel mit Status + Dateimanager
- Spulen-Trocknung & Materialmanagement (ACE)
- Konfigurierbarer MQTT-Modus („nur beim Drucken“, dauerhaft, deaktiviert)

---

## 📦 Installation über HACS (empfohlen)

1. **HACS → Integrationen → ⋯ → Custom Repositories**
2. Repository:  
   https://github.com/Caps3n/hass-anycubic_cloud_v3  
   Kategorie: **Integration**
3. **Daten neu laden**
4. Integration in HACS suchen:  
   **Anycubic HA Integration**
5. Installieren → Home Assistant **neustarten**
6. **Einstellungen → Geräte & Dienste → Integration hinzufügen**

> ⚠️ Wähle als Auth-Methode: **Slicer Next (Windows)**  
> und füge den **Access-Token** ein (siehe unten).

---

## 🖐️ Manuelle Installation

1. Repository als ZIP herunterladen  
2. Entpacken nach:  
   /config/custom_components/anycubic_ha_integration/
3. Home Assistant neu starten
4. Integration hinzufügen wie oben

---

## 🔐 Token auslesen (Slicer Next)

1. **Slicer Next starten → einloggen → schließen**
2. Öffne:  
   %AppData%\AnycubicSlicerNext\AnycubicSlicerNext.conf
3. PowerShell-Befehl (kopiert Token in Zwischenablage):
   ```powershell
   $path = "$env:AppData\AnycubicSlicerNext\AnycubicSlicerNext.conf"; 
   (Select-String -Path $path -Pattern '"access_token"\s*:\s*"([^"]+)"').Matches.Groups[1].Value | Set-Clipboard
   ```
4. In Integration einfügen → fertig  
   (optional Token in Datei danach leeren: `"access_token": ""`)

---

## 🌐 Web-Login (ohne MQTT, nur Polling)

1. [Anycubic Cloud öffnen](https://cloud-universe.anycubic.com/file)  
2. Developer Tools → Konsole:  
   ```js
   window.localStorage["XX-Token"]
   ```
3. Token kopieren → Integration einfügen

> ⚠️ Hinweis: Diese Methode unterstützt **kein MQTT**, nur 1-Minuten-Updates.

---

## 📥 Releases

➡️ [Letztes Release ansehen](https://github.com/Caps3n/hass-anycubic_cloud_v3/releases/latest)

> 

---

## 🙌 Mitwirkende

- [@Caps3n](https://github.com/Caps3n) (dieser Fork)
- [@ljschmitt](https://github.com/ljschmitt) (Basis-Fork)
- [@WaresWichall](https://github.com/WaresWichall) (Original-Entwicklung)

---

## 📄 Lizenz

MIT License – frei für private und kommerzielle Nutzung. Siehe LICENSE-Datei.

---

## 💬 Feedback / Probleme

➡️ [Issue öffnen](https://github.com/Caps3n/hass-anycubic_cloud_v3/issues)

---

## ✅ Kompatibilität

- Home Assistant 2025.11.0 oder neuer
- Abwärtskompatibel bis v2025.10 getestet

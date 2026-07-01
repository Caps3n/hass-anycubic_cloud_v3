# Anycubic HA Integration

> 🗓️ **Fork von [@Caps3n](https://github.com/Caps3n) – April 2026**  
> Basiert auf dem Fork von [@ljschmitt](https://github.com/ljschmitt/hass-anycubic_cloud_v3), der wiederum auf [@WaresWichall](https://github.com/WaresWichall/hass-anycubic_cloud) aufbaut.  
> Aktuell getestet mit **Kobra X** – Feedback willkommen!

> 🗓️ **Update (01.07.2026):**  
> Eigenständige Umsetzung dreier Funktionen, die es inzwischen auch im Basis-Fork von @ljschmitt gibt: **Datei-Direktdruck ohne Upload**, ein **`migrate_entity_ids`-Service** für stabile Entity-IDs sowie eine **Pro-Drucker-Kamera-Zuordnung** im Options-Flow.

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
- **Kobra X Kamera-Support** via lokalem LAN-Stream (`http://{Drucker-IP}:18088/flv`)
- **Datei-Direktdruck** ohne HA-Upload (`print_file_local` / `print_file_udisk`)
- **`migrate_entity_ids`-Service** für stabile, englische Entity-IDs
- **Pro-Drucker-Kamera-Zuordnung** im Options-Flow (z. B. für Rinkhals/Moonraker-Webcams)

---

## 📚 Inhalt

- [🧵 Kompatible Drucker](#-kompatible-drucker)
- [⚙️ Funktionsweise](#-funktionsweise)
- [🎨 Frontend-Card](#-frontend-card)
- [📷 Kamera (Kobra X & lokaler LAN-Stream)](#-kamera-kobra-x--lokaler-lan-stream)
- [🖼️ Galerie](#-galerie)
- [🧩 Features](#-features)
- [🖨️ Datei-Direktdruck ohne Upload](#️-datei-direktdruck-ohne-upload)
- [🆔 Stabile Entity-IDs & migrate_entity_ids](#-stabile-entity-ids--migrate_entity_ids)
- [📦 Installation über HACS (empfohlen)](#-installation-über-hacs-empfohlen)
- [🖐️ Manuelle Installation](#-manuelle-installation)
- [🔐 Token auslesen (Slicer Next)](#-token-auslesen-slicer-next)
- [🌐 Web-Login (ohne MQTT, nur Polling)](#-web-login-ohne-mqtt-nur-polling)
- [📥 Releases](#-releases)
- [🙌 Mitwirkende](#-mitwirkende)
- [📄 Lizenz](#-lizenz)
- [💬 Feedback / Probleme](#-feedback--probleme)
- [☕ Unterstützen](#-unterstützen)
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

## 📷 Kamera (Kobra X & lokaler LAN-Stream)

Drucker wie der **Kobra X** haben eine eingebaute Kamera, die **lokal** über LAN streamt – nicht über die Anycubic Cloud. Damit die Kamera in Home Assistant angezeigt werden kann, muss die **lokale IP-Adresse** des Druckers einmalig eingetragen werden.

### Einrichtung

1. Am Drucker: **Einstellungen → Netzwerk → IP-Adresse** ablesen (z. B. `192.168.1.42`)
2. In HA: **Einstellungen → Geräte & Dienste → Anycubic → Konfigurieren**
3. Im Menü **„Kamera‑Einstellungen"** die LAN-IP eintragen
4. HA neu starten

Danach streamt die Entität `camera.anycubic_kobra_x_camera` direkt über `http://{IP}:18088/flv`.

> 💡 **Hinweis:** Drucker wie Kobra 2 / Kobra 3 verwenden weiterhin die Cloud-Kamera (Tencent IoT Video). Die LAN-IP wird nur als Fallback genutzt, wenn der Cloud-Token nicht verfügbar ist.

### Pro-Drucker-Kamera-Zuordnung (z. B. Rinkhals/Moonraker-Webcam)

Bei mehreren Druckern mit unterschiedlichen Kameraquellen kann zusätzlich pro Drucker eine beliebige Home-Assistant-`camera.*`-Entity zugeordnet werden — z. B. eine über die **MJPEG IP Camera**-Integration eingebundene Rinkhals/Moonraker-Webcam. Diese ersetzt dann die Kamera nur für den jeweiligen Drucker in der Nebenansicht des eingebauten Panels.

1. **Einstellungen → Geräte & Dienste → Anycubic → Konfigurieren → Kamera‑Einstellungen**
2. Für jeden konfigurierten Drucker steht ein eigenes Auswahlfeld für eine HA-Kamera-Entity zur Verfügung
3. Feld leer lassen, um bei diesem Drucker weiter die Standardkamera (LAN-Stream/Cloud) zu verwenden

Die Zuordnung erfolgt intern über die HA-Geräte-ID des Druckers (nicht die Anycubic-Drucker-ID), sodass keine manuelle YAML-Konfiguration nötig ist.

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

## 🖨️ Datei-Direktdruck ohne Upload

Die Services `print_file_local` und `print_file_udisk` starten eine bereits auf dem Drucker- bzw. USB-Speicher vorhandene Datei, ohne sie vorher über Home Assistant hochzuladen.

**Aufruf:** Entwicklerwerkzeuge → Dienste → `anycubic_ha_integration.print_file_local` bzw. `print_file_udisk`

| Feld | Pflicht | Beschreibung |
|---|---|---|
| `config_entry` / `device_id` / `printer_id` | ja | wie bei den anderen Services |
| `filename` | ja | vollständiger Dateiname (mit Endung) wie in der Dateiliste angezeigt |
| `filepath` | nein | Unterordner, falls die Datei nicht im Root liegt |
| `slot_number` | nein | ACE-Slotliste, z. B. `[1, 2]` |

> ⚠️ **ACE-Hinweis:** Anders als beim Cloud-Druck kann die Slotliste hier **nicht** gegen die tatsächliche Farbanzahl der Datei geprüft werden — die Anycubic-API liefert für Dateien auf Drucker-/USB-Speicher keine Material-Metadaten. Die Zuordnung wird stattdessen aus den **aktuell in den angegebenen Slots geladenen Spulen** gebaut (Farbe/Material der Spule, die gerade steckt). Die Slot-Reihenfolge muss also manuell zur Farbreihenfolge der Datei passen — sonst druckt der Drucker mit der falschen Farbe.

---

## 🆔 Stabile Entity-IDs & migrate_entity_ids

Neu angelegte Entities dieser Integration bekommen ab dieser Version eine **stabile, englische Entity-ID** vorgeschlagen (z. B. `sensor.kobra_x_curr_nozzle_temp`), unabhängig von der eingestellten HA-Sprache. Das verhindert, dass bei deutschsprachigem HA aus übersetzten Anzeigenamen zufällige deutsche Entity-IDs entstehen, die mit Dashboards/Automationen kollidieren können.

**Bereits bestehende** Entity-IDs werden dadurch **nicht** automatisch verändert. Wer vorhandene Entity-IDs auf das neue, stabile Format umstellen möchte, kann den Service `anycubic_ha_integration.migrate_entity_ids` nutzen:

1. Entwicklerwerkzeuge → Dienste → `anycubic_ha_integration.migrate_entity_ids`
2. Zuerst mit `dry_run: true` (Standard) ausführen und die geplanten Umbenennungen im HA-Log prüfen
3. Erst wenn die geplanten Änderungen passen, erneut mit `dry_run: false` ausführen
4. Danach eigene Dashboards, Karten, Automationen und Skripte auf die neuen Entity-IDs prüfen

Der Service benennt ausschließlich Entity-Registry-Einträge dieser Integration um; Kollisionen mit bereits belegten Entity-IDs werden übersprungen und geloggt.

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

## ☕ Unterstützen

Wenn dir diese Integration gefällt und du die Weiterentwicklung unterstützen möchtest:

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-caps3n-yellow?logo=buy-me-a-coffee&logoColor=white)](https://www.buymeacoffee.com/caps3n)

---

## ✅ Kompatibilität

- Home Assistant 2025.11.0 oder neuer
- Abwärtskompatibel bis v2025.10 getestet

# VibedInsight → Google Play Store: Anleitung

Stand 2026-07-19. Was technisch schon erledigt ist und was **du** in der Play
Console tun musst. Paket: `com.vibedinsight.app`, Version 0.4.3 (versionCode 17).

---

## ✅ Schon erledigt (technisch)

- **Upload-Keystore**: `/home/spro/development/keystores/vibedinsight-upload.keystore`
  (Passwort im Session-Log / Passwortmanager). `key.properties` liegt gitignored.
- **Signiertes AAB** gebaut & im GitHub-Release:
  https://github.com/sprobst76/VibedInsight/releases/tag/v0.4.3 → `vibedinsight-v0.4.3.aab`
- **Privacy-Policy-URL (öffentlich)**: https://insight.lab.halbewahrheit21.de/privacy
- **CI**: `git tag vX.Y.Z` → baut signiertes AAB → GitHub-Release, und lädt in den
  Play-Internal-Track, **sobald** `PLAY_SERVICE_ACCOUNT_JSON`-Secret gesetzt ist.
- **App-Icon**: `app_icon_512.png` (Repo-Root, 512×512) für das Store-Icon.
- **Screenshots**: 2 Handy-Screenshots (Inbox, Artikel-Detail) — im Chat geschickt.

---

## 📋 Deine Schritte in der Play Console (erstmalig)

### 1. App anlegen
Play Console → **Alle Apps → App erstellen**
- App-Name: **VibedInsight**
- Standardsprache: **Deutsch (de-DE)** (Englisch als weitere Sprache später)
- App oder Spiel: **App** · Kostenlos: **Kostenlos**
- Erklärungen (Richtlinien/US-Exportgesetze) bestätigen.

### 2. Dashboard „App einrichten" durchgehen
- **App-Zugriff**: „Alle Funktionen sind eingeschränkt" → als Anweisung angeben:
  *„Client für einen selbst gehosteten VibedInsight-Server. Zum Testen Server-URL
  + API-Key unter Einstellungen eintragen."* (Für Internal Testing unkritisch.)
- **Anzeigen**: **Nein**, keine Werbung.
- **Inhaltseinstufung**: Fragebogen ausfüllen (Kategorie *Produktivität/Utility*,
  keine Gewalt/Sex/Drogen) → Ergebnis i.d.R. **USK 0 / Everyone**.
- **Zielgruppe**: **13+** (nicht für Kinder). „Familienprogramm": Nein.
- **Datensicherheit**: siehe Cheat-Sheet unten.
- **Datenschutzerklärung**: `https://insight.lab.halbewahrheit21.de/privacy`
- **Staatliche App / Finanzfunktionen / Gesundheit**: jeweils **Nein**.

### 3. Store-Eintrag (Haupt-Store-Eintrag)
- **Kurzbeschreibung / Vollständige Beschreibung**: Text unten (DE).
- **App-Icon**: `app_icon_512.png` (512×512).
- **Feature-Grafik (1024×500)**: musst du noch erstellen (Play verlangt sie fürs
  Listing). Einfacher Balken mit App-Name/Logo reicht. *(Sag Bescheid, ich kann
  eine schlichte generieren.)*
- **Handy-Screenshots**: die 2 aus dem Chat (min. 2, hochkant).
- **App-Kategorie**: **Produktivität** · Kontakt-E-Mail: deine.

### 4. Internes Testing → erster Upload (MANUELL)
Play Console → **Testen → Internal Testing → Neuen Release erstellen**
- **Play App Signing**: aktivieren/akzeptieren (Standard bei neuen Apps — Google
  hält den App-Signing-Key, dein Upload-Key signiert nur die Uploads).
- **App Bundle hochladen**: `vibedinsight-v0.4.3.aab` (aus dem GitHub-Release).
- Release-Notes eintragen (kurz), **Speichern → Überprüfen → Rollout**.
- **Tester**: E-Mail-Liste anlegen (deine Adresse) → Opt-in-Link öffnen, App über
  Play installieren.

⚠️ **Vor dem Play-Install die sideloadete App deinstallieren** (andere Signatur),
danach API-Key in den Einstellungen neu eintragen.

### 5. Danach: Auto-Updates aktivieren
1. ✅ **Service-Account = erledigt.** Kein neuer nötig — der vorhandene
   `github-play-deploy@noted-app-483813-u5.iam.gserviceaccount.com` (deployt auch
   ZenMail/Hush/VibedTracker) wird wiederverwendet; das GitHub-Secret
   `PLAY_SERVICE_ACCOUNT_JSON` ist im VibedInsight-Repo bereits gesetzt.
2. Play Console → **Nutzer & Berechtigungen** → prüfen, dass dieser Service-Account
   Zugriff auf VibedInsight hat (kontoweit → automatisch; sonst app-spezifisch Rolle
   „Releases in Test-Tracks verwalten" ergänzen).
3. Ab dann: **`git tag v0.4.4 && git push origin v0.4.4`** → CI lädt automatisch
   in Internal Testing. (Der allererste Upload MUSS manuell sein — Google-Regel.)

---

## 🔐 Data-Safety Cheat-Sheet (Antworten)

- **Werden Daten erhoben/geteilt?** Die App sendet Inhalte an den **selbst
  gehosteten Server des Nutzers** — der Entwickler erhebt/teilt **keine** Daten.
- Sammelt die App Daten? **Ja, aber nur an den eigenen Server des Nutzers**
  (bei „App-Aktivität/Nutzerinhalte": URLs/Notizen = *App-Funktionalität*, nicht
  mit Dritten geteilt, nicht verkauft).
- **Übertragung verschlüsselt?** Ja (HTTPS).
- **Löschung möglich?** Ja (Einträge in der App löschbar).
- Keine Standortdaten, keine Werbe-IDs, keine Analytics/Telemetrie.

---

## ✍️ Listing-Text

### Titel (max. 30)
`VibedInsight`

### Kurzbeschreibung DE (max. 80)
`Dein selbst gehostetes Wissensarchiv: Links & Notizen per KI zusammenfassen.`

### Vollständige Beschreibung DE (max. 4000)
```
VibedInsight ist dein persönliches, selbst gehostetes Wissensarchiv. Speichere
Links, Artikel und Notizen – die KI auf deinem eigenen Server fasst sie zusammen,
vergibt Themen und erkennt Zusammenhänge. Deine Daten bleiben bei dir.

FUNKTIONEN
• Links, Artikel und Notizen sammeln – auch per Teilen-Menü aus anderen Apps
• Automatische Zusammenfassungen auf Deutsch (über dein eigenes Ollama)
• Automatische Themen-Verschlagwortung
• Wochen-Digest der wichtigsten Erkenntnisse
• Knowledge-Graph: sieh, wie deine Inhalte zusammenhängen
• Suche, Favoriten, Gelesen-Status, Archiv

PRIVATSPHÄRE BY DESIGN
VibedInsight ist ein Client für deinen eigenen VibedInsight-Server. Es gibt keine
Cloud des Anbieters, kein Tracking, keine Werbung. Die KI-Verarbeitung läuft auf
deinem Server (Ollama), deine Inhalte verlassen deine Infrastruktur nicht.

HINWEIS
Diese App benötigt einen laufenden VibedInsight-Server (Backend). Server-URL und
API-Key trägst du in den Einstellungen ein.
```

### Kurzbeschreibung EN (max. 80)
`Your self-hosted knowledge archive: AI-summarize links & notes on your server.`

### Vollständige Beschreibung EN (max. 4000)
```
VibedInsight is your personal, self-hosted knowledge archive. Save links,
articles and notes — the AI on your own server summarizes them, assigns topics
and surfaces connections. Your data stays with you.

FEATURES
• Collect links, articles and notes — also via the Android share sheet
• Automatic summaries (via your own Ollama)
• Automatic topic tagging
• Weekly digest of your key takeaways
• Knowledge graph of how your content connects
• Search, favorites, read status, archive

PRIVACY BY DESIGN
VibedInsight is a client for your own VibedInsight server. No vendor cloud, no
tracking, no ads. AI processing runs on your server (Ollama); your content never
leaves your infrastructure.

NOTE
This app requires a running VibedInsight server (backend). Enter your server URL
and API key in the settings.
```

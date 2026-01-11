# VibedInsight - Testing Guide

## Automated Tests

### Test Structure

```
app/
├── test/                          # Unit and Widget tests
│   ├── fixtures/
│   │   └── test_fixtures.dart     # Sample test data
│   ├── helpers/
│   │   └── test_helpers.dart      # Testing utilities
│   ├── mocks/
│   │   └── mock_api_client.dart   # Mock implementations
│   ├── unit/
│   │   ├── models/
│   │   │   └── content_item_test.dart
│   │   └── providers/
│   │       └── items_state_test.dart
│   ├── widget/
│   │   └── item_card_test.dart
│   └── widget_test.dart
└── integration_test/
    └── app_test.dart              # Full app integration tests
```

### Running Tests

```bash
cd app

# All tests
flutter test

# Unit tests only
flutter test test/unit/

# Widget tests only
flutter test test/widget/

# Integration tests (requires device/emulator)
flutter test integration_test/

# With coverage
flutter test --coverage
```

### Test Summary

| Category | Tests | Description |
|----------|-------|-------------|
| Model Tests | 23 | JSON parsing, enums, computed properties |
| Provider Tests | 28 | ItemsState logic, filters, selection |
| Widget Tests | 19 | ItemCard rendering, interactions |
| **Total** | **70** | All passing |

### Writing New Tests

See `test/fixtures/test_fixtures.dart` for sample data and `test/helpers/test_helpers.dart` for utilities.

---

## Manual Test Checklist

### Ausstehende Tests

### v0.2.2 - Share Intent (Auto-Close)

- [ ] **Chrome Share Test**
  1. Öffne einen Artikel in Chrome
  2. Tippe auf "Teilen"
  3. Wähle "VibedInsight"
  4. **Erwartung:** App blitzt kurz auf und schließt sich sofort
  5. **Erwartung:** Notification "Processing: domain.com" erscheint
  6. **Erwartung:** Nach ~5-30 Sek. Notification "Added: [Titel]"

- [ ] **Andere Apps testen**
  - Twitter/X Share
  - YouTube Share
  - News App Share
  - Reddit Share

- [ ] **Edge Cases**
  - Share während Offline → Fehler-Notification?
  - Share einer ungültigen URL
  - Share von Text ohne URL
  - Mehrfach schnell hintereinander teilen

- [ ] **Notification Interaktion**
  - Tap auf "Added" Notification → Öffnet Item Detail?

### v0.2.0 - Knowledge Graph

- [ ] **Related Items im Server aktiviert?**
  ```bash
  curl https://insight.lab.halbewahrheit21.de/items/2/relations
  ```
  Falls 404: Server neu deployen mit `git pull && docker compose up -d --build`

- [ ] **Related Tab in App**
  - Öffne ein Item mit Topics
  - Wechsle zum "Related" Tab
  - Werden Items mit gemeinsamen Topics angezeigt?

### v0.2.0 - Search & Filter

- [ ] **Suche**
  - Tippe auf Lupe in der AppBar
  - Suche nach einem Begriff
  - Werden passende Items gefunden?
  - Debounce funktioniert (nicht bei jedem Buchstaben neu laden)?

- [ ] **Topic Filter**
  - Sind Topic-Chips unter der AppBar sichtbar?
  - Tippe auf einen Topic → Nur Items mit diesem Topic?
  - Tippe auf "All" → Alle Items wieder sichtbar?

### v0.2.0 - Notes

- [ ] **Note erstellen**
  - Tippe auf FAB "Add"
  - Wähle "Add Note"
  - Titel und Text eingeben
  - **Erwartung:** Note erscheint in der Liste

### v0.3.6 - Archive Functionality

- [ ] **Backend deployen**
  ```bash
  ssh server
  cd vibedinsight && git pull && docker compose up -d --build
  ```
  Das erstellt automatisch die `is_archived` Spalte.

- [ ] **Item archivieren (Swipe)**
  - Wische ein Item nach links
  - Tippe auf "Archive" (orange)
  - **Erwartung:** Item verschwindet aus der Liste
  - Snackbar zeigt "Item archived"

- [ ] **Archived-Filter**
  - Tippe auf "Archived" Filter-Chip
  - **Erwartung:** Nur archivierte Items werden angezeigt
  - Items haben "Unarchive" statt "Archive" im Swipe-Menü

- [ ] **Item wieder herstellen (Unarchive)**
  - Im Archived-Filter: Wische ein Item nach links
  - Tippe auf "Unarchive" (grün)
  - **Erwartung:** Item verschwindet aus der archivierten Ansicht
  - Ist jetzt wieder in "All" sichtbar

- [ ] **Bulk Archive**
  - Long-Press um Selection Mode zu aktivieren
  - Wähle mehrere Items
  - Tippe auf Archive-Icon in AppBar
  - **Erwartung:** Alle gewählten Items werden archiviert

- [ ] **Archivierte Items standardmäßig versteckt**
  - Ohne Filter zeigt die Liste KEINE archivierten Items
  - Nur "Archived" Filter zeigt sie an

### v0.3.5 - Bulk Actions

- [ ] **Backend deployen**
  ```bash
  ssh server
  cd vibedinsight && git pull && docker compose up -d --build
  ```

- [ ] **Selection Mode aktivieren**
  - Halte ein Item lange gedrückt (Long Press)
  - **Erwartung:** Selection Mode aktiviert, Item hat Checkbox
  - AppBar zeigt "1 selected" und Aktions-Buttons

- [ ] **Mehrere Items auswählen**
  - Tippe auf weitere Items
  - **Erwartung:** Checkboxen erscheinen, Zähler erhöht sich
  - "Select All" Button wählt alle sichtbaren Items

- [ ] **Bulk Mark as Read**
  - Wähle mehrere ungelesene Items
  - Tippe auf Brief-Icon in AppBar
  - **Erwartung:** Alle gewählten Items werden als gelesen markiert
  - Selection Mode beendet sich automatisch

- [ ] **Bulk Delete**
  - Wähle mehrere Items
  - Tippe auf Löschen-Icon in AppBar
  - **Erwartung:** Bestätigungsdialog erscheint
  - Nach Bestätigung: Items gelöscht, Selection Mode beendet

- [ ] **Selection Mode beenden**
  - Tippe auf X in der AppBar
  - **Erwartung:** Selection Mode beendet, normale Ansicht

- [ ] **UI während Selection Mode**
  - FAB ("Add") ist versteckt
  - Filter-Chips sind versteckt
  - Swipe-to-Delete ist deaktiviert

### v0.3.4 - Reading Progress

- [ ] **Backend deployen**
  ```bash
  ssh server
  cd vibedinsight && git pull && docker compose up -d --build
  ```
  Das erstellt automatisch die `is_read` Spalte.

- [ ] **Item als gelesen markieren (Liste)**
  - Tippe auf das Brief-Icon neben einem Item
  - **Erwartung:** Icon wechselt von "unread" (farbig) zu "read" (grau)
  - Blauer Punkt neben Titel verschwindet
  - Erneut tippen → zurück zu ungelesen

- [ ] **Item als gelesen markieren (Detail)**
  - Öffne ein Item
  - Tippe auf das Brief-Icon in der AppBar
  - **Erwartung:** Icon-Status ändert sich

- [ ] **Unread-Filter**
  - Filter-Chips unter AppBar zeigen "Unread" Chip
  - Tippe auf "Unread"
  - **Erwartung:** Nur ungelesene Items werden angezeigt
  - Tippe auf "All" → Alle Items wieder sichtbar

- [ ] **Unread kombiniert mit Suche**
  - Aktiviere Unread-Filter
  - Suche nach einem Begriff
  - **Erwartung:** Suche nur innerhalb der ungelesenen Items

### v0.3.3 - Favorites

- [ ] **Backend deployen**
  ```bash
  ssh server
  cd vibedinsight && git pull && docker compose up -d --build
  ```
  Das erstellt automatisch die `is_favorite` Spalte.

- [ ] **Item als Favorit markieren (Liste)**
  - Tippe auf den Stern neben einem Item in der Liste
  - **Erwartung:** Stern wird gelb ausgefüllt
  - Erneut tippen → Stern wird grau (unfavorited)

- [ ] **Item als Favorit markieren (Detail)**
  - Öffne ein Item
  - Tippe auf den Stern in der AppBar
  - **Erwartung:** Stern-Status ändert sich

- [ ] **Favoriten-Filter**
  - Filter-Chips unter AppBar zeigen jetzt "Favorites" Chip
  - Tippe auf "Favorites"
  - **Erwartung:** Nur favorisierte Items werden angezeigt
  - Tippe auf "All" → Alle Items wieder sichtbar

- [ ] **Favoriten kombiniert mit Suche**
  - Aktiviere Favorites-Filter
  - Suche nach einem Begriff
  - **Erwartung:** Suche nur innerhalb der Favoriten

### v0.3.2 - Edit Items

- [ ] **Edit-Dialog öffnen**
  - Öffne ein Item im Detail Screen
  - Tippe auf das Menü (drei Punkte) → "Edit"
  - **Erwartung:** Dialog mit Title und Summary Feldern

- [ ] **Titel bearbeiten**
  - Ändere den Titel
  - Tippe "Save"
  - **Erwartung:** Titel wird in der Liste und Detail aktualisiert

- [ ] **Summary bearbeiten**
  - Ändere die Summary
  - Tippe "Save"
  - **Erwartung:** Summary wird im Detail aktualisiert

- [ ] **Validierung**
  - Lösche den Titel komplett
  - **Erwartung:** "Title is required" Fehlermeldung

### v0.3.1 - Sorting

- [ ] **Sort-Button in AppBar**
  - Tippe auf das Sort-Icon (zwischen Suche und Weekly)
  - **Erwartung:** Popup-Menü mit Date, Title, Status
  - Aktuell gewähltes Feld ist hervorgehoben

- [ ] **Sortierung wechseln**
  - Wähle "Title" → Items alphabetisch sortiert
  - Wähle "Status" → Items nach Status sortiert
  - Wähle "Date" → Zurück zur Standard-Sortierung

- [ ] **Sortier-Reihenfolge umschalten**
  - Tippe erneut auf das bereits gewählte Feld
  - **Erwartung:** Pfeil wechselt von ↓ zu ↑ (desc → asc)

### v0.3.0 - Weekly Summary

- [ ] **Backend deployen**
  ```bash
  ssh server
  cd vibedinsight && git pull && docker compose up -d --build
  ```
  Das erstellt automatisch die `weekly_summaries` Tabelle.

- [ ] **Weekly Screen öffnen**
  - Tippe auf das ✨ Icon in der AppBar (rechts neben Suche)
  - **Erwartung:** Weekly Summary Screen öffnet sich
  - **Erwartung:** Zeigt "Current Week" mit Datumsbereich
  - **Erwartung:** Zeigt Anzahl Items und Processed Items

- [ ] **Summary generieren**
  - Falls noch kein Summary generiert wurde: Button "Generate Summary" sichtbar
  - Tippe auf "Generate Summary"
  - **Erwartung:** Loading-Spinner während Generierung (kann 30-60 Sek dauern)
  - **Erwartung:** Danach Summary-Text, Key Insights und Top Topics

- [ ] **Nach Generierung**
  - Summary-Text mit 2-3 Paragraphen
  - Key Insights als Liste mit Bullet Points
  - Top Topics als Chips

- [ ] **Pull-to-Refresh**
  - Nach unten ziehen → Refresht die Daten

---

## Bekannte Einschränkungen

1. **Share Auto-Close**: Falls App zu schnell stirbt, könnte Erfolgs-Notification fehlen (URL wird trotzdem verarbeitet)

2. **Knowledge Graph**: Funktioniert nur wenn Items gemeinsame Topics haben. Bei wenig Daten keine Relations.

3. **Offline**: Keine Offline-Unterstützung. Alle Aktionen brauchen Server-Verbindung.

---

## Feedback

Bei Problemen bitte notieren:
- Was wurde versucht?
- Was war das erwartete Verhalten?
- Was ist stattdessen passiert?
- Screenshot/Fehlermeldung wenn möglich

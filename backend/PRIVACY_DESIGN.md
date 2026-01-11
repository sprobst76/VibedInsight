# VibedInsight - Privacy & Security Design

## Problemstellung

VibedInsight verarbeitet persönliche Inhalte (Artikel, Notizen, Lesezeichen) serverseitig mit KI.
**Zero Knowledge ist nicht möglich**, weil Ollama die Rohdaten sehen muss.

Ziel: **Minimal Knowledge** - Server sieht nur das absolut Nötige, so kurz wie möglich.

---

## Analyse: Privacy-Konzepte

### 1. Zero Knowledge (❌ nicht umsetzbar)
- Server sieht nie Klartext
- Problem: Ollama braucht Klartext für Summarization
- Wäre nur mit Client-seitigem LLM möglich (zu ressourcenintensiv)

### 2. Minimal Knowledge (✅ empfohlen)
- Server sieht Daten nur während Verarbeitung
- Rohdaten werden nach Processing gelöscht
- Nur Metadaten + Summary bleiben

### 3. Encryption at Rest (✅ ergänzend)
- Datenbank-Verschlüsselung
- Schützt gegen physischen Zugriff auf Server
- Schützt NICHT gegen Server-Kompromittierung

### 4. Client-Side Encryption (⚠️ teilweise möglich)
- User verschlüsselt vor Upload
- Server kann verschlüsselte Daten nicht verarbeiten
- Möglich für: Notizen die NICHT verarbeitet werden sollen

### 5. Self-Hosting Option (✅ für Power-User)
- User betreibt eigenen Server
- Maximale Kontrolle
- Kein Vertrauen in Dritte nötig

### 6. Transparency & Control (✅ essentiell)
- User sieht genau was gespeichert ist
- User kann jederzeit alles löschen
- Vollständiger Datenexport

---

## Empfohlene Architektur: "Minimal Knowledge"

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATENLEBENSZYKLUS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. INGESTION          2. PROCESSING         3. STORAGE        │
│  ─────────────         ──────────────        ──────────        │
│                                                                 │
│  URL/Text kommt an     Ollama verarbeitet    Nur behalten:     │
│  ↓                     ↓                     ↓                 │
│  raw_text temporär     Summary generieren    - title           │
│  gespeichert           Topics extrahieren    - summary         │
│  (max 24h)             ↓                     - topics          │
│                        raw_text LÖSCHEN      - source_url      │
│                                              - created_at      │
│                                                                 │
│  ════════════════════════════════════════════════════════════  │
│                                                                 │
│  OPTIONAL: Encrypted Notes (Client-Side Encryption)            │
│  ───────────────────────────────────────────────────            │
│  - User verschlüsselt Notiz im Client                          │
│  - Server speichert nur Ciphertext                             │
│  - Keine serverseitige Verarbeitung möglich                    │
│  - User muss Schlüssel sicher aufbewahren                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Konkrete Maßnahmen

### Phase 1: Data Minimization (Backend)

#### 1.1 Rohdaten-Löschung nach Processing
```python
# Nach erfolgreicher Verarbeitung:
item.raw_text = None  # Löschen!
item.status = ProcessingStatus.COMPLETED
await db.commit()
```

**Vorteil**: Server speichert keine Originaltexte mehr
**Nachteil**: Reprocessing nicht möglich (akzeptabel)

#### 1.2 Metadaten minimieren
Speichern:
- `title` (vom Server extrahiert oder User-Input)
- `summary` (KI-generiert)
- `topics` (KI-extrahiert)
- `source_url` (für Quellenangabe)
- `created_at`, `updated_at`

NICHT speichern:
- IP-Adressen (nur temporär für Rate-Limiting)
- User-Agent (nur für Session-Tracking, nicht langfristig)
- Vollständige Browsing-History

#### 1.3 Automatische Datenbereinigung
```python
# Cron-Job: Lösche alte, nicht verarbeitete Items
async def cleanup_stale_data():
    # Items die >24h PENDING sind und raw_text haben
    cutoff = datetime.utcnow() - timedelta(hours=24)
    await db.execute(
        update(ContentItem)
        .where(ContentItem.created_at < cutoff)
        .where(ContentItem.raw_text.isnot(None))
        .values(raw_text=None)
    )
```

---

### Phase 2: Transparency Dashboard

#### 2.1 Daten-Übersicht Endpoint
```python
@router.get("/privacy/my-data")
async def get_my_data_summary(user: User):
    """Zeigt dem User exakt was gespeichert ist."""
    return {
        "account": {
            "email": user.email,
            "created_at": user.created_at,
            "last_login": user.last_login,
        },
        "content": {
            "items_count": await count_items(user.id),
            "total_size_bytes": await calculate_storage(user.id),
            "oldest_item": ...,
            "newest_item": ...,
        },
        "sessions": {
            "active_sessions": await count_active_tokens(user.id),
        },
        "data_retention": {
            "raw_text_stored": False,  # Nach Processing gelöscht
            "summaries_stored": True,
            "retention_period": "Until manual deletion",
        }
    }
```

#### 2.2 Vollständiger Datenexport
```python
@router.get("/privacy/export")
async def export_all_my_data(user: User):
    """GDPR Article 20: Recht auf Datenübertragbarkeit."""
    return {
        "export_date": datetime.utcnow().isoformat(),
        "user": UserExport(user),
        "items": [ItemExport(i) for i in user.content_items],
        "weekly_summaries": [...],
    }
```

#### 2.3 Granulare Löschoptionen
```python
@router.delete("/privacy/data/items")
async def delete_all_items(user: User):
    """Lösche alle Content Items."""

@router.delete("/privacy/data/summaries")
async def delete_weekly_summaries(user: User):
    """Lösche alle Weekly Summaries."""

@router.delete("/privacy/data/sessions")
async def revoke_all_sessions(user: User):
    """Beende alle aktiven Sessions."""
```

---

### Phase 3: Encrypted Notes (Optional Feature)

Für Notizen die der User NICHT verarbeiten lassen will:

#### 3.1 Client-Side Encryption
```dart
// Flutter Client
class EncryptedNote {
  static Future<String> encrypt(String plaintext, String userKey) async {
    // AES-256-GCM
    final key = await deriveKey(userKey);
    final nonce = generateSecureRandom(12);
    final ciphertext = await aesGcmEncrypt(plaintext, key, nonce);
    return base64Encode(nonce + ciphertext);
  }

  static Future<String> decrypt(String encrypted, String userKey) async {
    final data = base64Decode(encrypted);
    final nonce = data.sublist(0, 12);
    final ciphertext = data.sublist(12);
    final key = await deriveKey(userKey);
    return await aesGcmDecrypt(ciphertext, key, nonce);
  }
}
```

#### 3.2 Backend speichert nur Ciphertext
```python
class ContentItem:
    # Neues Feld
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    # raw_text enthält dann Ciphertext
```

#### 3.3 Key Management
- Key wird NIE zum Server gesendet
- Key wird im Secure Storage des Geräts gespeichert
- Optional: Key aus Passwort ableiten (PBKDF2)
- **Warnung**: Key verloren = Daten verloren

---

### Phase 4: Self-Hosting Support

#### 4.1 Einfache Deployment-Option
```yaml
# docker-compose.selfhost.yml
services:
  vibedinsight:
    image: ghcr.io/user/vibedinsight:latest
    environment:
      - DATABASE_URL=sqlite:///./data/vibedinsight.db
      - OLLAMA_BASE_URL=http://ollama:11434
    volumes:
      - ./data:/app/data

  ollama:
    image: ollama/ollama
    volumes:
      - ./ollama:/root/.ollama
```

#### 4.2 Dokumentation
- Schritt-für-Schritt Anleitung
- Raspberry Pi Support
- Backup-Strategien

---

### Phase 5: Trust Signals

#### 5.1 Privacy Policy (klar & verständlich)
```markdown
## Was wir speichern
- Email (für Login)
- Zusammenfassungen deiner Inhalte
- Themen/Tags

## Was wir NICHT speichern
- Originaltexte (werden nach Verarbeitung gelöscht)
- IP-Adressen (nur temporär)
- Tracking-Daten

## Wer hat Zugriff
- Nur du (über dein Passwort)
- Keine Weitergabe an Dritte
- Keine Werbung
```

#### 5.2 Open Source
- Code ist öffentlich einsehbar
- Jeder kann verifizieren was passiert
- Community-Audits möglich

#### 5.3 Keine Analytics
- Kein Google Analytics
- Kein Facebook Pixel
- Keine Drittanbieter-Scripts

---

## Implementierungsplan

### Priorität 1: Essentiell
| Feature | Aufwand | Impact |
|---------|---------|--------|
| Rohdaten nach Processing löschen | Gering | Hoch |
| Account-Löschung (bereits implementiert) | ✅ | Hoch |
| Datenexport Endpoint | Mittel | Hoch |
| Privacy Policy | Gering | Hoch |

### Priorität 2: Empfohlen
| Feature | Aufwand | Impact |
|---------|---------|--------|
| Transparency Dashboard | Mittel | Mittel |
| Session-Management UI | Mittel | Mittel |
| Automatische Datenbereinigung | Gering | Mittel |

### Priorität 3: Optional
| Feature | Aufwand | Impact |
|---------|---------|--------|
| Encrypted Notes | Hoch | Mittel |
| Self-Hosting Docs | Mittel | Für Power-User |

---

## Vergleich mit Alternativen

| Feature | VibedInsight (geplant) | Pocket | Instapaper | Notion |
|---------|------------------------|--------|------------|--------|
| Open Source | ✅ | ❌ | ❌ | ❌ |
| Self-Hostable | ✅ | ❌ | ❌ | ❌ |
| Rohdaten-Löschung | ✅ | ❌ | ❌ | ❌ |
| Datenexport | ✅ | ✅ | ✅ | ✅ |
| Account-Löschung | ✅ | ✅ | ✅ | ✅ |
| Keine Tracker | ✅ | ❌ | ❌ | ❌ |
| E2E Encryption | Teilweise | ❌ | ❌ | ❌ |

---

## Fazit

**Minimal Knowledge** ist der beste Kompromiss zwischen Funktionalität und Privacy:

1. **Daten werden verarbeitet** - unvermeidbar für KI-Features
2. **Rohdaten werden gelöscht** - nur Ergebnisse bleiben
3. **User hat volle Kontrolle** - Export, Löschung, Übersicht
4. **Transparenz** - Open Source, keine versteckten Tracker
5. **Self-Hosting Option** - für maximale Kontrolle

Dieses Modell gibt dem User **echtes Vertrauen**:
- Er weiß genau was gespeichert wird
- Er kann alles exportieren und löschen
- Er kann den Code selbst prüfen
- Er kann selbst hosten wenn gewünscht

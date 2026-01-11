# VibedInsight - Privacy Design V2: Anonymous Content Store

## Kernidee

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ANONYMOUS CONTENT ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   CONTENT STORE (anonym)              USER VAULT (verschlüsselt)        │
│   ─────────────────────               ──────────────────────────        │
│                                                                         │
│   ┌──────────────────┐               ┌──────────────────────────┐       │
│   │ content_items    │               │ user_vaults              │       │
│   │ ────────────────│               │ ──────────────────────── │       │
│   │ id (UUID)        │               │ user_id                  │       │
│   │ url              │               │ encrypted_refs (blob)    │       │
│   │ title            │      ????     │ vault_key_hash           │       │
│   │ summary          │◄─────────────►│                          │       │
│   │ topics           │  Zuordnung    │ (Nur User kann           │       │
│   │ created_at       │  unbekannt!   │  entschlüsseln)          │       │
│   │                  │               │                          │       │
│   │ NO user_id!      │               └──────────────────────────┘       │
│   └──────────────────┘                                                  │
│                                                                         │
│   Ein DB-Dump zeigt NICHT welcher User welche Artikel hat!              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Detailliertes Design

### 1. Content Store (Öffentlich/Anonym)

```sql
CREATE TABLE content_items (
    -- Zufällige UUID, nicht inkrementell (verhindert Enumeration)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content (kein User-Bezug!)
    url TEXT,
    url_hash TEXT UNIQUE,  -- SHA256(url) für Deduplizierung
    title TEXT,
    summary TEXT,
    source TEXT,

    -- Verarbeitung
    status TEXT,
    processed_at TIMESTAMP,

    -- Referenz-Zähler (für Garbage Collection)
    ref_count INTEGER DEFAULT 1,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
    -- KEIN user_id!
    -- KEIN updated_at (würde Zugriffsmuster verraten)
);

CREATE TABLE content_topics (
    content_id UUID REFERENCES content_items(id),
    topic_id INTEGER REFERENCES topics(id)
);
```

### 2. User Vault (Verschlüsselt)

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE,
    password_hash TEXT,

    -- Vault-Schlüssel (verschlüsselt mit User-Passwort)
    encrypted_vault_key TEXT,
    vault_key_salt TEXT,

    -- Anti-Flooding
    daily_submission_count INTEGER DEFAULT 0,
    last_submission_reset DATE,

    created_at TIMESTAMP
);

CREATE TABLE user_vault_entries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),

    -- Verschlüsselte Content-Referenz
    -- Enthält: content_id, added_at, is_favorite, is_read, etc.
    encrypted_data TEXT,

    -- Für Sortierung (nicht verschlüsselt, aber harmlos)
    created_at TIMESTAMP
);
```

### 3. Verschlüsselungsschema

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         KEY DERIVATION                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   User Passwort                                                         │
│        │                                                                │
│        ▼                                                                │
│   ┌─────────────────────┐                                               │
│   │ PBKDF2 (100k iter)  │──────► Auth Key (für Login)                   │
│   │ + Salt              │                                               │
│   └─────────────────────┘                                               │
│        │                                                                │
│        ▼                                                                │
│   ┌─────────────────────┐                                               │
│   │ HKDF (Expand)       │──────► Vault Key (für Verschlüsselung)        │
│   └─────────────────────┘                                               │
│                                                                         │
│   Vault Key verschlüsselt/entschlüsselt alle Vault Entries              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4. Vault Entry Struktur

```python
# Was im encrypted_data steht (nach Entschlüsselung)
class VaultEntry:
    content_id: UUID          # Referenz zum anonymen Content
    added_at: datetime        # Wann hinzugefügt
    is_favorite: bool
    is_read: bool
    is_archived: bool
    user_title: str | None    # Optional: User's eigener Titel
    user_notes: str | None    # Optional: User's Notizen
```

---

## Ablauf: Content hinzufügen

```
┌────────┐         ┌────────┐         ┌──────────────┐     ┌─────────────┐
│ Client │         │ Server │         │ Content Store│     │ User Vault  │
└───┬────┘         └───┬────┘         └──────┬───────┘     └──────┬──────┘
    │                  │                     │                    │
    │ 1. POST /ingest  │                     │                    │
    │    {url, vault_  │                     │                    │
    │     encrypted_   │                     │                    │
    │     entry}       │                     │                    │
    │─────────────────►│                     │                    │
    │                  │                     │                    │
    │                  │ 2. Check url_hash   │                    │
    │                  │────────────────────►│                    │
    │                  │                     │                    │
    │                  │ 3a. EXISTS: Get ID  │                    │
    │                  │◄────────────────────│                    │
    │                  │    (ref_count++)    │                    │
    │                  │                     │                    │
    │                  │ 3b. NEW: Extract,   │                    │
    │                  │    Process, Store   │                    │
    │                  │────────────────────►│                    │
    │                  │◄────────────────────│                    │
    │                  │    (new UUID)       │                    │
    │                  │                     │                    │
    │                  │ 4. Store encrypted  │                    │
    │                  │    vault entry      │                    │
    │                  │─────────────────────────────────────────►│
    │                  │                     │                    │
    │ 5. OK {id}       │                     │                    │
    │◄─────────────────│                     │                    │
    │                  │                     │                    │
```

### Client-seitige Verschlüsselung

```dart
// Flutter Client
class VaultService {
  late SecretKey _vaultKey;

  /// Vault Key aus Passwort ableiten
  Future<void> deriveVaultKey(String password, String salt) async {
    final pbkdf2 = Pbkdf2(
      macAlgorithm: Hmac.sha256(),
      iterations: 100000,
      bits: 256,
    );
    _vaultKey = await pbkdf2.deriveKey(
      secretKey: SecretKey(utf8.encode(password)),
      nonce: base64Decode(salt),
    );
  }

  /// Vault Entry verschlüsseln (vor dem Senden an Server)
  Future<String> encryptVaultEntry(VaultEntry entry) async {
    final algorithm = AesGcm.with256bits();
    final nonce = algorithm.newNonce();
    final plaintext = jsonEncode(entry.toJson());

    final secretBox = await algorithm.encrypt(
      utf8.encode(plaintext),
      secretKey: _vaultKey,
      nonce: nonce,
    );

    return base64Encode(secretBox.concatenation());
  }

  /// Vault Entry entschlüsseln (nach dem Laden vom Server)
  Future<VaultEntry> decryptVaultEntry(String encrypted) async {
    final algorithm = AesGcm.with256bits();
    final data = base64Decode(encrypted);

    final secretBox = SecretBox.fromConcatenation(
      data,
      nonceLength: 12,
      macLength: 16,
    );

    final plaintext = await algorithm.decrypt(
      secretBox,
      secretKey: _vaultKey,
    );

    return VaultEntry.fromJson(jsonDecode(utf8.decode(plaintext)));
  }
}
```

---

## Anti-Flooding Maßnahmen

### 1. Rate Limiting pro User (Server-seitig)

```python
class User:
    daily_submission_count: int
    last_submission_reset: date

MAX_DAILY_SUBMISSIONS = 50  # Anpassbar

async def check_rate_limit(user: User) -> bool:
    today = date.today()

    if user.last_submission_reset != today:
        user.daily_submission_count = 0
        user.last_submission_reset = today

    if user.daily_submission_count >= MAX_DAILY_SUBMISSIONS:
        raise HTTPException(429, "Daily limit reached")

    user.daily_submission_count += 1
    return True
```

### 2. Content Deduplizierung

```python
# Gleiche URL = gleicher Content (ref_count erhöhen)
async def get_or_create_content(url: str) -> ContentItem:
    url_hash = hashlib.sha256(url.encode()).hexdigest()

    existing = await db.get(ContentItem, url_hash=url_hash)
    if existing:
        existing.ref_count += 1
        return existing

    # Neuen Content erstellen
    return await create_and_process_content(url)
```

### 3. Storage Quotas pro User

```python
MAX_VAULT_ENTRIES = 10000  # Pro User

async def check_storage_quota(user_id: int) -> bool:
    count = await db.count(UserVaultEntry, user_id=user_id)
    if count >= MAX_VAULT_ENTRIES:
        raise HTTPException(402, "Storage quota exceeded")
    return True
```

### 4. Garbage Collection (orphaned Content)

```python
# Cron-Job: Lösche Content ohne Referenzen
async def garbage_collect():
    # Content mit ref_count=0 und älter als 30 Tage
    cutoff = datetime.utcnow() - timedelta(days=30)
    await db.execute(
        delete(ContentItem)
        .where(ContentItem.ref_count == 0)
        .where(ContentItem.created_at < cutoff)
    )
```

---

## Sicherheitsanalyse

### Was ein Angreifer mit DB-Zugang sieht:

| Daten | Sichtbar? | Zuordnung zu User? |
|-------|-----------|-------------------|
| Alle URLs/Artikel | ✅ Ja | ❌ Nein |
| User Emails | ✅ Ja | - |
| Welcher User welche Artikel hat | ❌ Nein | ❌ Verschlüsselt |
| User Favoriten/Read-Status | ❌ Nein | ❌ Verschlüsselt |
| User Notizen | ❌ Nein | ❌ Verschlüsselt |

### Angriffsvektoren:

| Angriff | Schutz |
|---------|--------|
| DB Dump | User-Content-Zuordnung verschlüsselt |
| Timing Attack (Zugriffsmuster) | Kein updated_at auf Content |
| Brute-Force Vault Key | PBKDF2 mit 100k Iterationen |
| Flooding | Rate-Limits + Quotas |
| URL Enumeration | UUIDs statt inkrementelle IDs |

### Verbleibendes Risiko:

- **Server sieht Content während Verarbeitung** - unvermeidbar
- **Kompromittierter Server kann neue Einträge mitlesen** - Lösung: Client-only Mode
- **Metadaten-Analyse** (Anzahl Einträge pro User) - minimal

---

## Implementierungsplan

### Phase 1: Basis-Architektur
1. Content Store ohne user_id umbauen
2. User Vault Tabelle erstellen
3. Client-seitige Verschlüsselung implementieren
4. Neue API Endpoints

### Phase 2: Migration
1. Bestehende Daten migrieren
2. User Vaults initialisieren
3. Alte user_id Spalte entfernen

### Phase 3: Härtung
1. Rate Limiting
2. Garbage Collection
3. Storage Quotas
4. Audit Logging (anonymisiert)

---

## API Design

### Neue Endpoints

```
POST /auth/register
  - Generiert vault_key_salt
  - Client sendet encrypted_vault_key

POST /auth/login
  - Gibt vault_key_salt zurück
  - Client kann Vault Key ableiten

POST /content
  - Anonym, nur URL
  - Gibt content_id zurück

POST /vault/entries
  - encrypted_data (vom Client verschlüsselt)
  - Enthält content_id Referenz

GET /vault/entries
  - Gibt alle encrypted_data zurück
  - Client entschlüsselt lokal

DELETE /vault/entries/{id}
  - Löscht Referenz
  - Decrementiert ref_count auf Content
```

---

## Offene Fragen

1. **Key Recovery**: Was wenn User Passwort vergisst?
   - Option A: Kein Recovery (maximale Sicherheit)
   - Option B: Recovery Key bei Registrierung (User muss aufbewahren)
   - Option C: Email-basiertes Recovery (schwächt Sicherheit)

2. **Shared Content**: Sollen User Content teilen können?
   - Würde Zuordnung teilweise aufheben
   - Könnte opt-in sein

3. **Suche**: Wie sucht User in seinen verschlüsselten Einträgen?
   - Client-seitig (alle Einträge laden, lokal suchen)
   - Searchable Encryption (komplex)
   - Unverschlüsselte Suchindizes (Kompromiss)

---

## Fazit

Diese Architektur bietet **echte Privatsphäre**:

1. **DB-Dump ist nutzlos** für User-Content-Zuordnung
2. **Server-Kompromittierung** gibt nur verschlüsselte Referenzen preis
3. **Anonym eingereichter Content** - kein direkter User-Bezug
4. **Anti-Flooding** durch Rate-Limits und Quotas
5. **Client kontrolliert Verschlüsselung** - Server hat keinen Vault Key

Trade-off: Höhere Komplexität, Client muss mehr Logik haben.

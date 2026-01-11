# VibedInsight - Privacy Design (Final)

## Entscheidungen

| Aspekt | Entscheidung |
|--------|--------------|
| Key Recovery | Recovery Codes bei Registrierung (wie 2FA) |
| Suche | Über Topics + Datum (unverschlüsselt für Performance) |
| Sharing | Summaries mit Links teilen (Content ist ohnehin anonym) |

---

## Finale Architektur

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATENMODELL                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐          ┌─────────────────────────────────────┐  │
│  │ CONTENT STORE       │          │ USER VAULT                          │  │
│  │ (anonym, öffentlich)│          │ (verschlüsselt, privat)             │  │
│  ├─────────────────────┤          ├─────────────────────────────────────┤  │
│  │                     │          │                                     │  │
│  │ content_items       │          │ users                               │  │
│  │ ───────────────     │          │ ─────                               │  │
│  │ id: UUID            │          │ id, email, password_hash            │  │
│  │ url, url_hash       │          │ vault_key_salt                      │  │
│  │ title, summary      │          │ recovery_codes_hash                 │  │
│  │ source              │          │ daily_submission_count              │  │
│  │ status              │          │                                     │  │
│  │ ref_count           │          │ user_vault_entries                  │  │
│  │ created_at          │          │ ──────────────────                  │  │
│  │                     │          │ id, user_id                         │  │
│  │ topics (M2M)        │◄─ ??? ──►│ encrypted_data ◄── AES-256-GCM      │  │
│  │                     │          │ created_at (für Sortierung)         │  │
│  │ ⛔ KEIN user_id     │          │ topic_ids[] (für Filterung)         │  │
│  │                     │          │                                     │  │
│  └─────────────────────┘          └─────────────────────────────────────┘  │
│                                                                             │
│  DB-Dump zeigt:                   DB-Dump zeigt:                           │
│  ✅ Alle Artikel                   ✅ User Emails                           │
│  ✅ Alle Summaries                 ✅ Welche Topics ein User nutzt          │
│  ❌ Wer welchen Artikel hat        ❌ Welche konkreten Artikel              │
│                                    ❌ Favoriten, Read-Status, Notizen       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Datenbank-Schema

### Content Store (anonym)

```sql
-- Anonymer Content ohne User-Bezug
CREATE TABLE content_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- URL Deduplizierung
    url TEXT,
    url_hash TEXT UNIQUE,  -- SHA256(normalized_url)

    -- Inhalt
    title TEXT,
    summary TEXT,
    source TEXT,  -- Domain

    -- Verarbeitung
    status TEXT DEFAULT 'pending',
    raw_text TEXT,  -- Temporär, wird nach Processing gelöscht
    processed_at TIMESTAMPTZ,

    -- Referenz-Zähler für Garbage Collection
    ref_count INTEGER DEFAULT 1,

    -- Nur created_at, KEIN updated_at (Zugriffsmuster)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Topics sind global (shared)
CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE content_topics (
    content_id UUID REFERENCES content_items(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (content_id, topic_id)
);

-- Index für Deduplizierung
CREATE INDEX idx_content_url_hash ON content_items(url_hash);
```

### User Vault (verschlüsselt)

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,

    -- Vault-Verschlüsselung
    vault_key_salt TEXT NOT NULL,  -- Für PBKDF2

    -- Recovery Codes (gehashed, wie 2FA)
    recovery_codes_hash TEXT[],  -- Array von 10 gehashten Codes
    recovery_codes_used BOOLEAN[] DEFAULT ARRAY[false,false,false,false,false,false,false,false,false,false],

    -- Anti-Flooding
    daily_submission_count INTEGER DEFAULT 0,
    last_submission_reset DATE DEFAULT CURRENT_DATE,
    vault_entry_count INTEGER DEFAULT 0,  -- Für Quota

    -- Account
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE TABLE user_vault_entries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,

    -- Verschlüsselter Payload (Client verschlüsselt)
    -- Enthält: content_id, is_favorite, is_read, is_archived, user_notes
    encrypted_data TEXT NOT NULL,

    -- Unverschlüsselt für Suche/Filterung (Kompromiss)
    created_at TIMESTAMPTZ DEFAULT NOW(),  -- Für Datum-Sortierung
    topic_ids INTEGER[] DEFAULT '{}',       -- Für Topic-Filterung

    -- Verhindert Duplikate
    content_hash TEXT,  -- Hash der content_id (nicht die ID selbst!)
    UNIQUE(user_id, content_hash)
);

-- Indizes für Suche
CREATE INDEX idx_vault_user ON user_vault_entries(user_id);
CREATE INDEX idx_vault_created ON user_vault_entries(user_id, created_at DESC);
CREATE INDEX idx_vault_topics ON user_vault_entries USING GIN(topic_ids);
```

---

## Verschlüsseltes Payload

```python
# Was encrypted_data enthält (nach Entschlüsselung)
class VaultEntryPayload:
    content_id: UUID          # Referenz zum anonymen Content
    is_favorite: bool = False
    is_read: bool = False
    is_archived: bool = False
    user_notes: str | None    # Private Notizen
    added_at: datetime        # Wann hinzugefügt
```

**Wichtig**: Die `content_id` ist verschlüsselt! Ein Angreifer mit DB-Zugang sieht:
- User hat 5 Vault Entries
- Die Entries haben Topics [1, 3] und [2, 5]
- Aber NICHT welche konkreten Artikel das sind

---

## Recovery Codes

### Bei Registrierung generiert

```python
def generate_recovery_codes() -> tuple[list[str], list[str]]:
    """
    Generiert 10 Recovery Codes.
    Gibt zurück: (plain_codes für User, hashed_codes für DB)
    """
    plain_codes = []
    hashed_codes = []

    for _ in range(10):
        # Format: XXXX-XXXX-XXXX (wie 2FA)
        code = "-".join(
            "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
            for _ in range(3)
        )
        plain_codes.append(code)
        hashed_codes.append(hash_recovery_code(code))

    return plain_codes, hashed_codes

def hash_recovery_code(code: str) -> str:
    """Hash mit bcrypt (langsam, gegen Brute-Force)."""
    return bcrypt.hash(code.replace("-", "").upper())
```

### Bei Registrierung anzeigen

```
╔════════════════════════════════════════════════════════════════════╗
║                     🔐 RECOVERY CODES                               ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  Diese Codes sind deine EINZIGE Möglichkeit, dein Konto           ║
║  wiederherzustellen, wenn du dein Passwort vergisst.              ║
║                                                                    ║
║  ⚠️  WICHTIG: Speichere sie JETZT an einem sicheren Ort!          ║
║  ⚠️  Sie werden NIE WIEDER angezeigt!                             ║
║                                                                    ║
║  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐       ║
║  │ ABCD-EFGH-JKLM │  │ NPQR-STUV-WXYZ │  │ 2345-6789-ABCD │       ║
║  └────────────────┘  └────────────────┘  └────────────────┘       ║
║  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐       ║
║  │ EFGH-JKLM-NPQR │  │ STUV-WXYZ-2345 │  │ 6789-ABCD-EFGH │       ║
║  └────────────────┘  └────────────────┘  └────────────────┘       ║
║  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐       ║
║  │ JKLM-NPQR-STUV │  │ WXYZ-2345-6789 │  │ ABCD-EFGH-JKLM │       ║
║  └────────────────┘  └────────────────┘  └────────────────┘       ║
║  ┌────────────────┐                                               ║
║  │ NPQR-STUV-WXYZ │                                               ║
║  └────────────────┘                                               ║
║                                                                    ║
║  [ ] Ich habe meine Recovery Codes gespeichert                    ║
║                                                                    ║
║                    [Weiter zur App]                                ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
```

### Recovery Flow

```
1. User klickt "Passwort vergessen"
2. User gibt Email + Recovery Code ein
3. Server prüft:
   - Ist der Code korrekt? (bcrypt verify)
   - Wurde er schon benutzt? (recovery_codes_used[i])
4. Wenn OK:
   - Code als "benutzt" markieren
   - User setzt neues Passwort
   - WICHTIG: Vault Key muss neu abgeleitet werden!
   - Alle Vault Entries müssen mit neuem Key re-encrypted werden
```

**Problem**: Bei Passwort-Reset muss der Client alle Entries entschlüsseln (alter Key) und neu verschlüsseln (neuer Key). Das geht nur wenn der User den alten Key noch kennt (z.B. auf anderem Gerät eingeloggt).

**Lösung**: Recovery Code enthält auch den Vault Key (verschlüsselt):

```python
# Bei Registrierung
vault_key = generate_random_key()  # 256 bit
encrypted_vault_key = encrypt(vault_key, derived_key_from_password)

# Recovery Codes verschlüsseln den Vault Key separat
for code in recovery_codes:
    code_key = derive_key(code)
    encrypted_vault_key_for_recovery[i] = encrypt(vault_key, code_key)
```

---

## Sharing: Summaries mit Links

Da Content anonym ist, kann man ihn einfach teilen:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          SHARE SUMMARY                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  📄 "Die Zukunft der KI in der Medizin"                                │
│                                                                         │
│  Summary:                                                               │
│  Künstliche Intelligenz revolutioniert die medizinische Diagnostik...  │
│                                                                         │
│  Topics: #AI #Healthcare #Technology                                    │
│                                                                         │
│  Original: https://example.com/article                                  │
│                                                                         │
│  ───────────────────────────────────────────────────────────────────── │
│                                                                         │
│  Share Link: https://vibedinsight.app/s/abc123                         │
│                                                                         │
│  [📋 Copy Link]  [📱 Share]  [❌ Close]                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Privacy**: Der Share-Link enthält nur die Content-ID. Niemand kann sehen, WELCHER User geteilt hat.

---

## API Endpoints

### Auth

```
POST /auth/register
  Request:  { email, password }
  Response: { user_id, vault_key_salt, recovery_codes[] }

POST /auth/login
  Request:  { email, password }
  Response: { access_token, refresh_token, vault_key_salt }

POST /auth/recover
  Request:  { email, recovery_code, new_password }
  Response: { success, encrypted_vault_key }  -- Key verschlüsselt mit Recovery Code
```

### Content (anonym)

```
POST /content
  Request:  { url }
  Response: { content_id, title, summary, topics[], status }
  Note:     Kein Auth nötig für Content-Erstellung!
            (Rate-Limit über IP, nicht User)

GET /content/{id}
  Response: { id, title, summary, source, topics[] }
  Note:     Öffentlich, jeder kann Content lesen

GET /content/{id}/share
  Response: { share_url }
```

### Vault (verschlüsselt)

```
POST /vault/entries
  Auth:     Required
  Request:  { encrypted_data, topic_ids[] }
  Response: { entry_id, created_at }

GET /vault/entries
  Auth:     Required
  Query:    ?topic_id=X&from_date=Y&to_date=Z
  Response: { entries: [{ id, encrypted_data, created_at, topic_ids }] }

DELETE /vault/entries/{id}
  Auth:     Required
  Effect:   Löscht Entry, decrementiert ref_count auf Content
```

---

## Anti-Flooding Limits

| Limit | Wert | Scope |
|-------|------|-------|
| Submissions/Tag | 50 | Pro User |
| Max Vault Entries | 10.000 | Pro User |
| Content Size | 100KB | Pro Artikel |
| Rate Limit (anon) | 10/min | Pro IP |
| Rate Limit (auth) | 100/min | Pro User |

---

## Implementierungsreihenfolge

### Phase 1: Schema-Migration
1. ~~user_id aus content_items entfernen~~ → Neues Schema ohne
2. user_vault_entries Tabelle erstellen
3. Recovery Codes Spalten hinzufügen

### Phase 2: Backend
1. Vault Key Derivation (PBKDF2)
2. Recovery Code Generierung
3. Neue API Endpoints
4. Content Deduplizierung (url_hash)
5. Garbage Collection Job

### Phase 3: Flutter Client
1. Vault Key Management
2. Client-seitige Verschlüsselung (AES-256-GCM)
3. Recovery Code Anzeige bei Registrierung
4. Recovery Flow

### Phase 4: Migration bestehender Daten
1. Für jeden User: Vault Key generieren
2. Bestehende Items → Vault Entries konvertieren
3. user_id aus content_items entfernen
4. ref_count berechnen

---

## Zusammenfassung

| Feature | Status |
|---------|--------|
| Anonymer Content Store | ✅ Design fertig |
| Verschlüsselter User Vault | ✅ Design fertig |
| Recovery Codes | ✅ Design fertig |
| Suche über Topics + Datum | ✅ Design fertig |
| Summary Sharing | ✅ Design fertig |
| Anti-Flooding | ✅ Design fertig |

**Nächster Schritt**: Mit der Implementierung beginnen?

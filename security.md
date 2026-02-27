# Security Report — DetectiveBoard

**Data:** 2026-02-27
**Scope:** analisi statica dell'intero codice sorgente (`app.py`, templates, JS)
**Metodologia:** revisione manuale del codice, nessun test dinamico
**Ipotesi:** autenticazione basata su **username** (non email)

---

## Contesto

L'app espone endpoint REST autenticati tramite JWT (Bearer token). Non usa cookie di sessione, il che elimina il rischio classico di CSRF. Avendo un flusso di registrazione/login aperto al pubblico, le vulnerabilità legate all'autenticazione e alla gestione degli utenti sono quelle con il maggiore impatto reale.

---

## Sul commento Reddit

> "the signup flow isn't tied to real authentication since I could register with a random email"

Con un sistema basato su **username**, questo commento perde completamente di rilevanza. Non esiste più il problema di "registrarsi con l'identità di qualcun altro": uno username è un identificatore arbitrario scelto dall'utente, non un dato che appartiene a terzi. L'unica conseguenza dell'assenza di un canale email è l'impossibilità di recuperare la password dimenticata (vedi punto #3).

---

## Vulnerabilità — Top 10 per priorità

---

### 1. Secret key JWT con fallback insicuro
**Priorità: ALTA** — compromette l'intera autenticazione

**File:** `app.py`, riga 24
```python
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
```

Se la variabile d'ambiente `SECRET_KEY` non è impostata in produzione, tutti i JWT vengono firmati con una chiave pubblica e nota. Un attaccante può forgiare token validi per qualsiasi `user_id`, ottenendo accesso a qualunque account senza conoscere la password.

**Fix:**
```python
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set")
```

---

### 2. Nessun rate limiting sugli endpoint di autenticazione
**Priorità: ALTA** — espone a brute force

**File:** `app.py`, righe 126–177 (register e login)

Non esiste alcun limite al numero di richieste su `/api/auth/login` e `/api/auth/register`. Un attaccante può:
- Tentare milioni di password contro un account noto (brute force)
- Creare migliaia di account automaticamente (spam/bot)

**Fix:** aggiungere [Flask-Limiter](https://flask-limiter.readthedocs.io/):
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=get_remote_address)

@limiter.limit("10 per minute")
@app.route("/api/auth/login", methods=["POST"])
def login(): ...
```

---

### 3. Nessun meccanismo di recupero account
**Priorità: ALTA** — utenti bloccati permanentemente

Con un sistema a username, non esiste un canale out-of-band (email, SMS) per verificare l'identità dell'utente al di fuori della password. Questo comporta:
- Password dimenticata = account perso per sempre
- Impossibilità di notificare gli utenti in caso di data breach
- Impossibilità di forzare un reset password se una credenziale risulta compromessa

**Fix:** richiedere un indirizzo email opzionale (o obbligatorio solo per il recupero), conservato separatamente dall'identità pubblica (username). L'email non viene mai mostrata ad altri utenti ma viene usata esclusivamente per il reset password tramite token monouso con scadenza breve.

---

### 4. Header HTTP di sicurezza assenti
**Priorità: MEDIA-ALTA** — protezioni di base mancanti

**File:** `app.py` (globale)

L'applicazione non imposta nessun header di sicurezza. I principali mancanti:

| Header | Protezione |
|---|---|
| `Content-Security-Policy` | XSS, injection |
| `X-Frame-Options: DENY` | Clickjacking |
| `X-Content-Type-Options: nosniff` | MIME sniffing |
| `Referrer-Policy: no-referrer` | Leak di URL |
| `Permissions-Policy` | Accesso a sensori/camera |

**Fix:** aggiungere un `after_request` hook:
```python
@app.after_request
def set_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline';"
    )
    return response
```

---

### 5. Upload file: validazione solo sull'estensione, non sul contenuto
**Priorità: MEDIA** — bypass possibile

**File:** `app.py`, righe 349–350 e 407–408
```python
ext = file.filename.rsplit(".", 1)[-1].lower()
if ext not in ("jpg", "jpeg", "png"):
    ...
```

L'estensione è banalmente falsificabile: un file `.php` rinominato `.jpg` supera il controllo. Se il web server è configurato male (es. esegue file in `static/uploads/`), un attaccante può caricare codice eseguibile.

**Fix:** validare i magic bytes del file oltre all'estensione, usando la libreria `python-magic`:
```python
import magic
mime = magic.from_buffer(file.read(2048), mime=True)
file.seek(0)
if mime not in ("image/jpeg", "image/png"):
    return jsonify({"error": "Tipo file non valido"}), 400
```

---

### 6. Nessun limite di dimensione server-side per i file caricati
**Priorità: MEDIA** — DoS da disco pieno

**File:** `app.py` (configurazione Flask)

La UI dice "max 1 MB" ma il server non impone nessun limite. Un attaccante può inviare direttamente richieste HTTP con file da gigabyte, esaurendo lo spazio su disco.

**Fix:** aggiungere alla configurazione Flask:
```python
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB
```
Flask rifiuterà automaticamente le richieste più grandi con 413.

---

### 7. Validazione del colore bypassabile nel JSON PUT
**Priorità: MEDIA** — bypass della whitelist

**File:** `app.py`, righe 421–424

Il form `multipart/form-data` valida il colore contro `ALLOWED_CARD_COLORS` (riga 400), ma il percorso JSON non lo fa:
```python
for field in ("pos_x", "pos_y", "title", "description", "color"):
    if field in data:
        fields.append(f"{field} = %s")
        values.append(data[field])  # color non validato!
```

Un attaccante può impostare `color` a qualsiasi valore arbitrario, aggirando la whitelist e potenzialmente rompendo il rendering o iniettando valori inattesi nel DOM.

**Fix:** aggiungere la validazione nel ramo JSON:
```python
if "color" in data:
    color = data["color"] if data["color"] in ALLOWED_CARD_COLORS else None
    fields.append("color = %s")
    values.append(color)
```

---

### 8. Nessuna policy sulla complessità della password
**Priorità: BASSA** — password deboli permesse

**File:** `app.py`, riga 133
```python
if len(password) < 8:
    return jsonify({"error": "Password must be at least 8 characters"}), 400
```

"12345678" è una password valida. Non ci sono controlli su varietà di caratteri, pattern comuni, o password già note come compromesse.

**Fix:** come minimo, richiedere almeno una lettera maiuscola, un numero e un carattere speciale. Per una protezione più solida, verificare la password contro il database HaveIBeenPwned tramite la loro API k-anonymity (che non rivela la password in chiaro).

---

### 9. Token di condivisione in chiaro nel DB senza scadenza
**Priorità: BASSA** — superficie di attacco permanente

**File:** `app.py`, riga 619

Il token di condivisione viene generato con `secrets.token_urlsafe(24)` (corretto) ma:
- È memorizzato in chiaro nella colonna `share_token` del database
- Non ha data di scadenza
- Un link creato mesi fa e dimenticato rimane valido per sempre

Se il database venisse compromesso, tutti i link di condivisione attivi sarebbero immediatamente accessibili.

**Fix:**
- Aggiungere una colonna `share_expires_at` con scadenza configurabile
- Opzionalmente, memorizzare solo l'hash del token nel DB (come si fa con i token di reset password)

---

### 10. Username enumeration tramite messaggi di errore distinti
**Priorità: MINIMA** — impatto trascurabile

**File:** `app.py`, riga 150

La risposta "Username already taken" permette tecnicamente di scoprire quali username esistono nel sistema. Tuttavia, a differenza dell'email enumeration, gli username sono per natura identificatori pubblici (visibili ad altri utenti sulla piattaforma): l'informazione che trapela è già accessibile altrove. Il rischio residuo è trascurabile salvo requisiti di privacy molto stringenti.

**Fix (opzionale):** restituire un messaggio generico solo se la privacy degli username è un requisito esplicito del prodotto.

---

## Riepilogo

| # | Vulnerabilità | Priorità | Sforzo fix |
|---|---|---|---|
| 1 | Fallback `SECRET_KEY` insicuro | Alta | Basso |
| 2 | Nessun rate limiting auth | Alta | Basso |
| 3 | Nessun recupero account (no email) | Alta | Medio |
| 4 | Header HTTP di sicurezza assenti | Media-Alta | Basso |
| 5 | Upload: solo estensione validata | Media | Medio |
| 6 | Nessun limite dimensione upload | Media | Basso |
| 7 | Color bypass in JSON PUT | Media | Basso |
| 8 | Nessuna policy password | Bassa | Basso |
| 9 | Share token senza scadenza | Bassa | Medio |
| 10 | Username enumeration | Minima | Basso |

**Aspetti già corretti (da non toccare):**
- SQL injection: tutti i parametri usano query parametrizzate (`%s`) con psycopg2 ✓
- Ownership check: ogni endpoint verifica che la risorsa appartenga all'utente loggato ✓
- Password hashing: Werkzeug `generate_password_hash` con PBKDF2 ✓
- Token JWT: algoritmo HS256, scadenza 30 giorni ✓
- Nomi file upload: UUID casuale invece del nome originale ✓
- Share token generation: `secrets.token_urlsafe(24)` con entropia adeguata ✓

# Piano: email → username

## Contesto

Il campo `email` nella tabella `users` viene riutilizzato come identificatore libero (username). L'obiettivo è eliminare ogni riferimento visibile a "email" nell'interfaccia e nelle API, proibire il carattere `@` in registrazione (così da impedire l'inserimento di indirizzi email reali), e trattare il valore esistente come uno username opaco. Il DB non cambia: la colonna resta `email`, ma il suo contenuto viene esposto ovunque come `username`.

**Decisioni prese:**
- Case-insensitive: `.lower()` rimane, comportamento invariato
- API: cambio netto, nessuna backward compat (solo browser)
- UI: mostra lo username così com'è, senza prefisso `@`

---

## File da modificare (7 file totali)

### 1. `app.py`

**`register()` (righe 126–155):**
- `data.get("email")` → `data.get("username")`
- Aggiungere validazione: `if "@" in username: return jsonify({"error": "Username cannot contain @"}), 400`
- Errori: `"Email and password are required"` → `"Username and password are required"`
- Errore duplicate: `"Email already registered"` → `"Username already taken"`
- Response JSON: chiave `"email"` → `"username"` (il valore rimane `user["email"]` dal DB)
- La query SQL INSERT non cambia (la colonna DB si chiama ancora `email`)

**`login()` (righe 158–177):**
- `data.get("email")` → `data.get("username")`
- Errori: `"Email and password are required"` → `"Username and password are required"`
- Errore auth: `"Invalid email or password"` → `"Invalid username or password"`
- Response JSON: chiave `"email"` → `"username"`
- La query SQL SELECT non cambia (`WHERE email = %s`)

**`get_me()` (righe 180–191):**
- La query SQL non cambia (`SELECT id, email FROM users`)
- Response: costruire il dict manualmente per rinominare la chiave: `{"id": user["id"], "username": user["email"]}`

---

### 2. `templates/home.html` (righe 147–148, 170–171)

- Label "Email" → "Username" (×2)
- `type="email"` → `type="text"` (×2)
- `id="login-email"` → `id="login-username"`
- `id="register-email"` → `id="register-username"`
- `name="email"` → `name="username"` (×2)
- `autocomplete="email"` → `autocomplete="username"` (×2)

---

### 3. `templates/index.html` (righe 15, 180–181, 203–204)

- `id="auth-email"` → `id="auth-username"` (span nell'header)
- Stesse modifiche dei form di home.html (label, type, id, name, autocomplete)

---

### 4. `templates/shared.html` (righe 16, 39–40, 62–63)

- `id="auth-email"` → `id="auth-username"` (span nell'header)
- Stesse modifiche dei form di home.html

---

### 5. `static/js/home.js`

- `document.getElementById('login-email')` → `getElementById('login-username')`
- `document.getElementById('register-email')` → `getElementById('register-username')`
- Variabili locali: `const email` → `const username` (×2)
- `JSON.stringify({ email, password })` → `JSON.stringify({ username, password })` (×2)
- `getElementById('login-email').focus()` → `getElementById('login-username').focus()`
- `getElementById('register-email').focus()` → `getElementById('register-username').focus()`

---

### 6. `static/js/board.js`

- Stesse modifiche getElementById e variabili di home.js
- Commento `// { id, email }` → `// { id, username }`
- `currentUser = { email: data.email }` → `{ username: data.username }` (×2, login e register)
- `document.getElementById('auth-email').textContent = currentUser.email`
  → `getElementById('auth-username').textContent = currentUser.username`

---

### 7. `static/js/shared.js`

- Stesse modifiche getElementById e variabili di home.js
- `document.getElementById('auth-email').textContent = user.email` → `auth-username` / `user.username` (×3: checkAuth, handleLogin, handleRegister)
- `JSON.stringify({ email, password })` → `{ username, password }` (×2)

---

## Verifica

1. **Avviare il server:** `uv run flask --app app run --debug`
2. **Registrazione:** aprire `/`, registrarsi con uno username senza `@` → deve funzionare, header mostra lo username
3. **Blocco `@`:** tentare registrazione con `pippo@gmail.com` → deve restituire errore 400
4. **Login:** login con lo username appena creato → deve funzionare
5. **Utenti esistenti:** login con una email precedente (es. `test@example.com`) → deve continuare a funzionare perché il valore è ancora nel DB, viene solo trattato come username
6. **Shared board:** aprire `/share/<token>`, fare login → header mostra username correttamente
7. **API `/api/auth/me`:** verificare che la risposta JSON contenga `username` e non `email`

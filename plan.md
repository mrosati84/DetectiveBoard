# Detective Board Plan

Detective Board Plan è una applicazione web che permette di gestire e risolvere casi di detective in modo efficiente e organizzato. L'obiettivo e' la creazione di una **board** "classica" da investigatore, di quelle in sughero sulle quali e' possibile pinnare vari elementi e creare collegamenti con il classico "filo rosso" tra di essi.

- L'applicazione **non e' collaborativa**, ma permette il **salvataggio** di varie board in un database SQL.
- L'applicazione e' progettata per **girare in locale**, per cui non e' necessario un sistema di autenticazione.
- L'applicazione dovra' tracciare tutti gli elementi, le loro posizioni e le loro connessioni col filo rosso per replicare fedelmente la board quando questa viene salvata e caricata.

## Stack

L'applicazione e' implementata usando il framework **Flask**, che servira' sia per servire le pagine HTML, sia per gestire gli API endpoint e la connessione al database SQL.

Il codice CSS e JS sono scritti plain, senza pre-processori o sistemi di build.

E' **obbligatorio** l'uso di `uv` sia per l'installazione dei pacchetti che per l'esecuzione degli script. L'applicazione **deve** usare `python-dotenv` per il caricamento delle variabili di ambiente e deve usare un file `.env` nella root di progetto.

I file statici dell'applicazione devono essere serviti da Flask.

### Database

L'applicazione deve usare alembic per gestire migrazioni del database ed assumere l'esistenza di un database postgresql locale a localhost:5432 con utente `postgres` e password `postgres`. Anche il database sara' `postgres`. Tutti questi dati devono provenire da variabili di ambiente.

## La board

La board ha lo sfondo in sughero. e' possibile aggiungere alla board tutti gli elementi descritti. Un asset e' presente nella directory `assets` e puoi usarlo.

### Layout

Il layout e' molto semplice. La board in sughero deve occupare il 100% in larghezza ed altezza e deve essere in "cover". Qualsiasi altro elemento deve essere flottante sopra la board di sughero.

#### Menu

Il menu e' flottante sulla sinistra. Dal menu e' possibile:

- **Caricare** board esistenti
- **Creare** una nuova board
- **Eliminare** board esistenti

Il menu puo' essere mostrato/nascosto (toggle).

#### Toolbar

La toolbar e' flottante in basso. Tramite la toolbar e' possibile creare gli elementi della board. La toolbar e' sempre visibile.

### Elemento: Card

La card e' l'elemento principale della board. I campi sono:

- `title`: obblibatorio, testo.
- `description`: opzionale, testo lungo.
- `image`: opzionale, file upload immagine (jp[e]g, png), max 1MB.

Il file di image deve essere salvato nel filesystem locale sotto la directory `static/uploads`.

Il layout della card prevede la presenza di un pin da board di sughero visibile sulla parte superiore. Questo non ha alcuna funzionalita' e' solo estetico.

#### Posizione del pin delle card

Il pin delle card puo' apparire in 3 posizioni sulla parte superiore della card:

1. In centro (default)
2. A sinistra
3. A destra

La posizione del pin puo' essere modificata tramite un apposito radio button quando la card viene modificata. È necessario, se già esistente, creare una migrazione per la card per gestire e mantenere salvata la posizione del pin della card.

la card prevede lo stato `selected` qualora la si clicchi. È possibile selezionare più card contemporaneamente tenendo premuto il tasto `SHIFT`.

La card può essere eliminata, se `selected`, premendo il tasto `DEL`. Se più card sono `selected`, verranno eliminate tutte. Usa un semplice `confirm` del browser per confermare l'azione. Se una card `selected` viene ri-selezionata, non sarà più selected.

#### Modificare una card

È possibile modificare una card esistente facendo doppio click. Al doppio click appare un pannello flottante sulla destra che permette di modificarne tutti i field. Al click su "Salva":

1. Il pannello si chiude.
2. La card nella board di sughero mostra i dati aggiornati (Incluso il ricalcolo della posizione del filo rosso, in base alla posizione del pin, se questo è stato modificato)

#### Collegamento delle card

Le card possono essere collegate tra loro tramite il classico *filo rosso* di lana delle board degli investigatori. Per collegare due card:

1. Le due card devono essere selezionate
2. Se due card sono selezionate (solo due, non possono essere connesse più di 2 card), apparirà un nuovo pulsante nella toolbar "Connetti".
3. Se una delle due card viene de-selezionata o se una terza o quarta card vengono selezionate, il pulsante scompare.
4. Se esattamente due card sono `selected` e l'utente preme il pulsante "Collega", le due card saranno ora collegate dal filo rosso.

#### Scollegare le card

Segue le stesse regole del collegamento. Se esattamente due card collegate sono `selected`, appare un pulsante "Scollega" che le scollegherà.

#### Spostare le card

Se una card viene tenuta "premuta" con il mouse sinistro e spostata, questa si sposterà nella board. Il collegamento tra le card deve essere ricollegato e ridisegnato al muoversi delle card.

##### Il filo rosso dell'investigatore

Il filo rosso non deve essere una banale linea rossa. Deve sembrare un filo di lana, e "sentire la gravità". Dovra' incurvarsi leggermente verso il basso simulando la leggera gravità che il filo sente.

Il filo rosso deve apparire **sopra** le card.

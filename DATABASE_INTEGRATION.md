# Integrazione Database MariaDB

## Panoramica

Il software AutoMediaOrganizer integra un modulo per la gestione dei dati elaborati tramite database MariaDB. Questa funzionalità permette di catalogare e tracciare tutti i file multimediali processati, gestire automaticamente i duplicati e mantenere un registro strutturato delle informazioni sui media.

## Caratteristiche Principali

### 1. Pattern Singleton
La classe `Database` è implementata come singleton, garantendo che esista una sola istanza della connessione al database durante l'esecuzione del programma. Questo assicura:
- Gestione efficiente delle connessioni
- Coerenza dei dati
- Riduzione del carico sul database

### 2. Schema Database

Il database utilizza 4 tabelle principali:

#### `movies`
Memorizza informazioni sui film:
- `tmdb_id`: ID univoco da TMDB
- `title`: Titolo del film
- `release_date`: Data di uscita
- `overview`: Descrizione
- Altri metadati (poster, valutazioni, ecc.)

#### `tv_shows`
Memorizza informazioni sulle serie TV:
- `tmdb_id`: ID univoco da TMDB
- `name`: Nome della serie
- `first_air_date`: Data prima messa in onda
- `overview`: Descrizione
- Altri metadati

#### `episodes`
Memorizza dettagli degli episodi:
- `tv_show_id`: Riferimento alla serie TV
- `season_number`: Numero stagione
- `episode_number`: Numero episodio
- `name`: Titolo dell'episodio
- Altri metadati

#### `files`
Registro dei file processati:
- `file_path`: Percorso originale del file
- `file_hash`: Hash SHA256 del file
- `destination_path`: Percorso di destinazione
- `media_type`: Tipo di media (movie/tv)
- Riferimenti a movie/tv_show/episode

### 3. Gestione Duplicati

Il sistema gestisce i duplicati in due modi:

1. **Per Percorso**: Verifica se un file con lo stesso path è già stato processato
2. **Per Hash**: Calcola l'hash SHA256 del file e controlla se un file identico esiste già nel catalogo

Quando viene rilevato un duplicato:
- Il file viene saltato automaticamente
- Viene registrato un messaggio nel log
- Le statistiche vengono aggiornate

### 4. Integrazione con il Flusso Esistente

L'integrazione del database è completamente opzionale e non invasiva:
- Se il database è disabilitato, il software funziona normalmente
- Se abilitato, i dati vengono salvati automaticamente durante il processamento
- Il sistema gestisce automaticamente errori di connessione

## Configurazione

### 1. Setup Database MariaDB

Prima di utilizzare l'integrazione, creare il database:

```sql
CREATE DATABASE automediaorganizer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'automedia_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON automediaorganizer.* TO 'automedia_user'@'localhost';
FLUSH PRIVILEGES;
```

### 2. Configurazione in config.toml

Aggiungere la sezione database nel file `Config/config.toml`:

```toml
[database]
enabled = true
host = "localhost"
port = 3306
user = "automedia_user"
password = "your_password"
database = "automediaorganizer"
```

### 3. Creazione Tabelle

Le tabelle vengono create automaticamente al primo avvio se non esistono già. Non è necessaria alcuna azione manuale.

## Utilizzo

### Abilitare l'Integrazione

Impostare `enabled = true` nella sezione `[database]` del file di configurazione.

### Disabilitare l'Integrazione

Impostare `enabled = false` per disabilitare completamente l'integrazione database. Il software continuerà a funzionare normalmente senza salvare dati nel database.

### Monitoraggio

I log forniscono informazioni dettagliate sull'attività del database:
- Connessioni stabilite
- Record inseriti/aggiornati
- Duplicati rilevati
- Errori di database

## Metodi della Classe Database

### Connessione
- `_connect()`: Stabilisce la connessione al database
- `_ensure_connection()`: Verifica e ripristina la connessione se necessario
- `close()`: Chiude la connessione

### Gestione Schema
- `create_tables()`: Crea tutte le tabelle necessarie

### Inserimento Dati
- `insert_movie(movie_data)`: Inserisce o aggiorna un film
- `insert_tv_show(tv_data)`: Inserisce o aggiorna una serie TV
- `insert_episode(tv_show_id, episode_data, season, episode)`: Inserisce o aggiorna un episodio
- `insert_file(file_path, destination_path, media_type, ...)`: Registra un file processato

### Controllo Duplicati
- `is_file_processed(file_path)`: Verifica se un file è già stato processato
- `is_duplicate_by_hash(file_path)`: Verifica duplicati tramite hash del file

### Query Dati
- `get_movie_by_tmdb_id(tmdb_id)`: Recupera dati di un film
- `get_tv_show_by_tmdb_id(tmdb_id)`: Recupera dati di una serie TV

## Gestione Errori

Il sistema gestisce automaticamente:
- Perdita di connessione (reconnect automatico)
- Errori di inserimento (rollback transazioni)
- Violazioni di constraint (update invece di insert)
- Database non disponibile (fallback a funzionamento senza DB)

## Note Tecniche

### Dipendenze
- `pymysql>=1.1.0`: Driver Python per MariaDB/MySQL

### Encoding
- Tutte le tabelle usano `utf8mb4_unicode_ci` per supportare caratteri internazionali

### Indici
- Indici ottimizzati su campi frequentemente ricercati (tmdb_id, title, hash, ecc.)

### Foreign Keys
- Relazioni tra tabelle con `ON DELETE CASCADE` o `SET NULL` appropriati

### Transazioni
- Uso di transazioni per garantire consistenza dei dati
- Rollback automatico in caso di errore

## Troubleshooting

### Errore di Connessione
Verificare:
- MariaDB in esecuzione
- Credenziali corrette
- Host e porta corretti
- Permessi utente database

### Tabelle Non Create
Verificare:
- Privilegi CREATE sulla database
- Log per messaggi di errore specifici

### Duplicati Non Rilevati
Il calcolo dell'hash può richiedere tempo per file grandi. Per file molto grandi, considera l'uso di un hash del percorso come fallback.

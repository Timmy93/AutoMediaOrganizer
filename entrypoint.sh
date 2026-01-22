#!/bin/bash

# Imposta valori di default se non specificati
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Crea il gruppo se non esiste
if ! getent group appuser > /dev/null 2>&1; then
    groupadd -g "$PGID" appuser
fi

# Crea l'utente se non esiste
if ! getent passwd appuser > /dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -m -s /bin/bash appuser
fi

# Assegna i permessi sulla directory /app
chown -R appuser:appuser /app

# Esegui il comando come appuser
exec gosu appuser "$@"
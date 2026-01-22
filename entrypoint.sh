#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "Starting with PUID=$PUID and PGID=$PGID"

# Rimuovi appuser se esiste già
if getent passwd appuser > /dev/null 2>&1; then
    userdel -f appuser 2>/dev/null || true
fi

if getent group appuser > /dev/null 2>&1; then
    groupdel appuser 2>/dev/null || true
fi

# Crea il gruppo con il PGID specificato
if ! getent group "$PGID" > /dev/null 2>&1; then
    groupadd -g "$PGID" appuser 2>/dev/null || groupadd --badname -g "$PGID" appuser
else
    # Se il gruppo con quel GID esiste già, usalo ma rinominalo
    existing_group=$(getent group "$PGID" | cut -d: -f1)
    if [ "$existing_group" != "appuser" ]; then
        groupmod -n appuser "$existing_group" 2>/dev/null || groupadd --badname -g "$PGID" appuser
    fi
fi

# Crea l'utente con il PUID specificato
if ! getent passwd "$PUID" > /dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -M -s /bin/bash appuser 2>/dev/null || \
    useradd --badname -u "$PUID" -g "$PGID" -M -s /bin/bash appuser
else
    # Se l'utente con quel UID esiste già, usalo ma rinominalo
    existing_user=$(getent passwd "$PUID" | cut -d: -f1)
    if [ "$existing_user" != "appuser" ]; then
        usermod -l appuser "$existing_user" 2>/dev/null || \
        useradd --badname -u "$PUID" -g "$PGID" -M -s /bin/bash appuser
    fi
fi

# Verifica l'utente creato
echo "Running as user: $(id appuser)"

# Assegna i permessi sulla directory /app
chown -R "$PUID":"$PGID" /app

# Esegui il comando come appuser
exec gosu appuser "$@"
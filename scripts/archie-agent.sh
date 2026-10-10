#!/usr/bin/env bash
# archie-agent launcher. install.sh replaces @PROJECT_DIR@ and installs this
# as /usr/local/bin/archie-agent (or ~/.local/bin/archie-agent).
# It deliberately does NOT cd anywhere: --allow-access-to-files defaults to
# the directory you ran the command from.

ARCHIE_HOME="@PROJECT_DIR@"
export ARCHIE_HOME

PY="$ARCHIE_HOME/venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "[!] Archie venv not found at $ARCHIE_HOME/venv" >&2
    echo "[i] Re-run: $ARCHIE_HOME/install.sh" >&2
    exit 1
fi

[ -d "$ARCHIE_HOME/MODELS" ] && export OLLAMA_MODELS="${OLLAMA_MODELS:-$ARCHIE_HOME/MODELS}"

exec "$PY" "$ARCHIE_HOME/archie_agent.py" "$@"

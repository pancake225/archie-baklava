#!/usr/bin/env bash
# ==========================================
#   Init-system compatibility helpers
#   systemd / OpenRC / runit / SysV / none
# ==========================================
# Sourced by install.sh and start.sh. Lets both scripts manage the
# Ollama service without assuming systemd is present.

detect_init_system() {
    if command -v systemctl &> /dev/null && [ -d /run/systemd/system ]; then
        echo "systemd"
    elif command -v rc-service &> /dev/null; then
        echo "openrc"
    elif command -v sv &> /dev/null && [ -d /etc/sv ]; then
        echo "runit"
    elif command -v service &> /dev/null; then
        echo "sysv"
    else
        echo "none"
    fi
}

# is_service_running <name>
is_service_running() {
    local name="$1"
    case "$(detect_init_system)" in
        systemd) systemctl is-active --quiet "$name" ;;
        openrc)  rc-service "$name" status &> /dev/null ;;
        runit)   sv status "$name" &> /dev/null ;;
        sysv)    service "$name" status &> /dev/null ;;
        none)    pgrep -x "$name" &> /dev/null ;;
    esac
}

# enable_and_start_service <name>   (used by install.sh — persists across reboots where possible)
enable_and_start_service() {
    local name="$1"
    local init
    init="$(detect_init_system)"
    echo "[i] Init system detected: $init"

    case "$init" in
        systemd)
            doas systemctl enable --now "$name" 2>/dev/null || sudo systemctl enable --now "$name" 2>/dev/null || true
            ;;
        openrc)
            doas rc-update add "$name" default 2>/dev/null || sudo rc-update add "$name" default 2>/dev/null || true
            doas rc-service "$name" start 2>/dev/null || sudo rc-service "$name" start 2>/dev/null || true
            ;;
        runit)
            doas ln -sf "/etc/sv/$name" "/etc/service/$name" 2>/dev/null || sudo ln -sf "/etc/sv/$name" "/etc/service/$name" 2>/dev/null || true
            doas sv start "$name" 2>/dev/null || sudo sv start "$name" 2>/dev/null || true
            ;;
        sysv)
            doas service "$name" start 2>/dev/null || sudo service "$name" start 2>/dev/null || true
            ;;
        none)
            echo "[!] No supported init system detected."
            echo "[i] Starting '$name' manually in the background instead."
            nohup "$name" serve > "/tmp/${name}_serve.log" 2>&1 &
            disown
            echo "[!] Note: '$name' will NOT auto-start on reboot this way."
            echo "    Add it to whatever startup mechanism your system uses"
            echo "    (cron @reboot, rc.local, a login script, etc.)"
            ;;
    esac
}

# configure_ollama_models_dir <models_dir>
# Exporting OLLAMA_MODELS in install.sh's own shell does NOT affect
# where models get pulled — 'ollama pull' just talks to the already
# -running daemon over HTTP, and that daemon has its own environment
# (set by whatever started it: systemd, OpenRC, ...), not ours. This
# function edits the *service's* environment and restarts it so the
# daemon itself actually uses our project's MODELS/ folder.
configure_ollama_models_dir() {
    local models_dir="$1"
    local init
    init="$(detect_init_system)"

    case "$init" in
        systemd)
            local override_dir="/etc/systemd/system/ollama.service.d"
            local override_file="$override_dir/override.conf"
            echo "[i] Writing systemd override so Ollama stores models in: $models_dir"
            doas mkdir -p "$override_dir" 2>/dev/null || sudo mkdir -p "$override_dir"
            printf '[Service]\nEnvironment="OLLAMA_MODELS=%s"\n' "$models_dir" \
                | (doas tee "$override_file" > /dev/null 2>&1 || sudo tee "$override_file" > /dev/null)
            doas systemctl daemon-reload 2>/dev/null || sudo systemctl daemon-reload
            doas systemctl restart ollama 2>/dev/null || sudo systemctl restart ollama
            sleep 2
            ;;
        openrc)
            local conf_file="/etc/conf.d/ollama"
            echo "[i] Setting OLLAMA_MODELS in $conf_file"
            (doas touch "$conf_file" 2>/dev/null || sudo touch "$conf_file")
            (doas sed -i '/^OLLAMA_MODELS=/d' "$conf_file" 2>/dev/null || sudo sed -i '/^OLLAMA_MODELS=/d' "$conf_file") 2>/dev/null
            echo "OLLAMA_MODELS=\"$models_dir\"" | (doas tee -a "$conf_file" > /dev/null 2>&1 || sudo tee -a "$conf_file" > /dev/null)
            doas rc-service ollama restart 2>/dev/null || sudo rc-service ollama restart 2>/dev/null || true
            sleep 2
            ;;
        runit|sysv)
            echo "[!] Can't automatically pin the models directory for '$init' yet."
            echo "    Ollama will use its own default model location for now."
            echo "    Set OLLAMA_MODELS=$models_dir wherever your $init service"
            echo "    definition sources its environment, then restart it."
            ;;
        none)
            echo "[i] No service manager detected — OLLAMA_MODELS is exported"
            echo "    directly in this shell and 'ollama serve' inherits it"
            echo "    correctly since we launch it ourselves."
            ;;
    esac
}

# start_service_if_needed <name>   (used by start.sh — just make sure it's up right now)
start_service_if_needed() {
    local name="$1"
    if is_service_running "$name"; then
        return 0
    fi

    local init
    init="$(detect_init_system)"
    echo "[!] $name is not running, starting..."

    case "$init" in
        systemd) doas systemctl start "$name" 2>/dev/null || sudo systemctl start "$name" ;;
        openrc)  doas rc-service "$name" start 2>/dev/null || sudo rc-service "$name" start ;;
        runit)   doas sv start "$name" 2>/dev/null || sudo sv start "$name" ;;
        sysv)    doas service "$name" start 2>/dev/null || sudo service "$name" start ;;
        none)
            nohup "$name" serve > "/tmp/${name}_serve.log" 2>&1 &
            disown
            sleep 2
            ;;
    esac
}
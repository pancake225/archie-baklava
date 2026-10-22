# Archie (arxh)

## Linux / macOS
    ./setup.sh        # wizard (or: python3 archie_setup.py)
    ./install.sh      # deps, models, installs the `archie-agent` command
    archie-agent --cli

## Windows
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    # open a NEW terminal, then:
    archie-agent --cli

## Flags (everything dangerous is OFF by default)
    --cli --gui --telegram --discord
    --allow-access-to-files --allow-access-to-internet --allow-access-to-apply
    --allow-shell --allow-email --allow-all --read-only --yes --workdir DIR --unrestricted-paths
    --provider local|groq|openrouter|both|local+openrouter|groq+openrouter|all
    --model NAME --groq-model NAME --openrouter-model ID --system-prompt TEXT --admin
    --mode default|performance|lightweight|compat
    --emoji/--no-emoji --vision/--no-vision --show-permissions
    archie-agent --help   for the full list

## Email (optional)

Email is separate from `--allow-all` because it is private data. To let the
agent read mail (read-only; messages are not marked as read), export the IMAP
credentials and add `--allow-email`:

    export ARCHIE_MAIL_HOST=imap.example.com
    export ARCHIE_MAIL_USER=you@example.com
    export ARCHIE_MAIL_PASSWORD=app-password
    archie-agent --cli --allow-email

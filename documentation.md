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
    --allow-shell --allow-all --read-only --yes --workdir DIR --unrestricted-paths
    --provider local|groq|openrouter|both|local+openrouter|all --model NAME --openrouter-model ID --system-prompt TEXT --admin
    --emoji/--no-emoji --vision/--no-vision --show-permissions
    archie-agent --help   for the full list

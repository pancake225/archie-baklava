# archie-baklava

A modular AI framework with multi-interface support, hybrid backend management, and cross-init Linux system integration.

## Features

- Multi-Interface Support: Native profiles for CLI, GUI (PyQt/Tkinter), Discord, and Telegram.
- Vision Capability: Multimodal vision processing for analyzing image inputs alongside text prompts.
- Hybrid LLM Backends: Modular core supporting multiple local and remote AI provider integrations.
- Multi-Init Compatibility: Built-in support and helper scripts for systemd, OpenRC, runit, and SysV init systems.
- Automated Setup: Embedded installation scripts for quick environment setup and dependency deployment.

## Project Structure

```text
archie-baklava/
├── ai_core.py             # Main AI backend logic and provider routing
├── vision.py              # Vision and image processing pipeline
├── main.py                # Main application entry point
├── arxh.conf              # Central configuration file
├── setup.sh               # Environment setup script
├── start.sh               # Execution entry wrapper
├── install.sh             # Dependency installer
├── profiles/              # Interface modules
│   ├── cli_profile.py     # Command-line interface
│   ├── gui_profile.py     # Graphical user interface
│   ├── discord_profile.py # Discord bot integration
│   └── telegram_profile.py# Telegram bot integration
└── scripts/
    └── init_compat.sh     # Init system compatibility layer

Prerequisites

    Operating System: Arch Linux (or any Linux distribution)

    Python: Version 3.10 or higher

    Git

Installation

1. Clone the repository:

    git clone [https://github.com/pancake225/archie-baklava.git](https://github.com/pancake225/archie-baklava.git)
    cd archie-baklava

2. Run the setup script to create the environment and install dependencies:

    chmod +x setup.sh install.sh start.sh
    ./setup.sh

Configuration

    Edit arxh.conf to configure your API keys, model backends, and interface settings:


PROFILE_TYPE="cli" #Your profile type
BOT_NAME="name" #Your bot's name 
BOT_TOKEN="" #Your telegram token (if profile type=telegram)
DISCORD_TOKEN="" #Your discord bot token (if profile type=discord)
DISCORD_CHANNEL_ID="0" #Your discord channel id 

and etc...

Usage

1.    Start the framework using the start script:

    ./start.sh

2.    Alternatively, launch specific interfaces directly via Python:

python main.py --profile cli
python main.py --profile gui
python main.py --profile discord
python main.py --profile telegram   

Init System Integration

To configure archie-baklava as a background service across different init systems:

sudo ./scripts/init_compat.sh --install
or doas ./scripts/init_compat.sh --install

Supported init managers:

    systemd

    OpenRC

    runit

    SysVinit

Good Luck!

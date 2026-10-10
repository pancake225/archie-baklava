# Security Policy

## Supported Versions

Only the latest release gets security fixes.

| Version  | Supported          |
| -------- | ------------------ |
| 0.5.x    | :white_check_mark: |
| < 0.5    | :x:                |

## Reporting a Vulnerability

**Please don't open a public issue for security problems.**

Report privately through one of these:

- GitHub: the **Security** tab → **Report a vulnerability** (private vulnerability reporting)
- Email: `<zippedpancake@tutamail.com>`

Please include:

- What the problem is and which version you're on
- Steps to reproduce (a minimal example is perfect)
- What an attacker could do with it
- Your OS and provider setup (Ollama / Groq / OpenRouter), if relevant

### What to expect

This is a small project maintained by one person, so these are goals, not guarantees:

| Step                         | Target                          |
| ---------------------------- | ------------------------------- |
| Acknowledgement of your report | within 3 days                 |
| First assessment (accepted / declined / need more info) | within 7 days |
| Status updates               | at least every 7 days until resolved |
| Fix for accepted issues      | depends on severity, critical ones first |

- **If accepted:** I'll work on a fix, tell you when it's released, and credit you in the release notes unless you'd rather stay anonymous.
- **If declined:** I'll explain why (for example: working as intended, out of scope, or can't be reproduced). You're welcome to reply with more details.

Please give me reasonable time to ship a fix before disclosing publicly.

## Scope

Things that count as vulnerabilities:

- Bypassing the `archie-agent` permission flags (for example, file or shell access without `--allow-access-to-files` / `--allow-shell`, or escaping `--workdir` without `--unrestricted-paths`)
- Running write or shell actions without the user's approval
- Leaking bot tokens or API keys (Telegram, Discord, Groq, OpenRouter) from `arxh.conf` or logs
- Command injection or unsafe handling of input in the installers and scripts
- Admin / banned-user checks that can be bypassed in the Telegram or Discord profiles

Usually **not** vulnerabilities:

- Behavior caused by the user turning on `--allow-all`, `--allow-shell` or `--yes`. These flags deliberately give the model real power
- Prompt injection that only makes the model say something wrong, without bypassing a permission check
- Problems in third-party services or software (Ollama, Groq, OpenRouter, Telegram, Discord) that should be reported to them
- Issues that need an attacker who already has full access to your machine or your `arxh.conf`

## Staying Safe

- Keep `arxh.conf` private. It contains tokens and keys, so never commit or share it
- Prefer the `GROQ_API_KEY` / `OPENROUTER_API_KEY` environment variables over command-line key flags, since flags end up in shell history
- Only grant the permissions a task needs, and use `--workdir` to limit file access
- Be careful with `--allow-shell` and `--yes` when Archie reads untrusted content, such as web pages or other people's files

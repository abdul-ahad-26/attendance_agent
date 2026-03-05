# MS Teams Auto-Join Attendance Agent

A Python agent that automatically joins your MS Teams classes on schedule so your attendance is always marked. Built with Playwright browser automation.

You configure your weekly timetable once, and the agent handles everything: navigating to the right team/channel, waiting for the meeting to start, muting mic, turning off camera, joining, staying for the duration, and leaving.

## How It Works

1. **Scheduler fires** 3 minutes before class time
2. **Navigates** to the correct Team > Channel in MS Teams web
3. **Polls** for an active meeting (checks every 15 seconds, waits up to 15 minutes)
4. **Joins** the meeting with mic muted and camera off
5. **Stays** in the meeting for the class duration
6. **Leaves** automatically when the class ends (or early if next class is starting)
7. **Sends notifications** (desktop toast + optional Discord) on join, leave, failure, or cancellation

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Microsoft Edge** (pre-installed on Windows)
- **uv** (Python package manager) - [install uv](https://docs.astral.sh/uv/getting-started/installation/)

### 1. Install uv (if you don't have it)

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and install

```bash
git clone <repo-url>
cd attendance_agent
uv sync
uv run playwright install msedge
```

That's it. `uv sync` creates a virtual environment, installs all dependencies with exact pinned versions from the lockfile - no version conflicts, no greenlet errors.

### 3. Configure your timetable

```bash
cp config/config.example.yaml config/config.yaml
```

The timetable for **AI 6th Semester (Batch 2023) - Spring 2026** is already filled in. Just open `config/config.yaml` and change the email to your roll number:

```yaml
student:
  email: "23-AI-XX@students.duet.edu.pk"    # <-- Change XX to your roll number
```

That's it. All 13 classes (Mon-Fri) are pre-configured with the correct team, channels, and timings.

> **Your `config.yaml` is gitignored** - it never gets pushed. Your email stays private.

### 4. Login (one-time)

```bash
uv run attendance-agent --login
```

This opens Edge and navigates to Teams. Log in manually. Your session is saved in `browser_data/` and persists across runs - you only need to do this once.

### 5. Test with a class

```bash
uv run attendance-agent --join-now "Data Structures (Mon)"
```

Use the exact class `name` from your config. This immediately tries to join that class (useful for testing during a live meeting).

### 6. Start the agent

```bash
uv run attendance-agent
```

This starts the scheduler. It runs in the foreground and auto-joins classes at the times in your timetable. Leave it running.

## All Commands

| Command | Description |
|---------|-------------|
| `uv run attendance-agent --login` | One-time browser login (saves session) |
| `uv run attendance-agent --join-now "Class Name"` | Immediately join a specific class |
| `uv run attendance-agent --pause` | Open Playwright Inspector to discover/debug selectors |
| `uv run attendance-agent` | Start the scheduled auto-join agent |
| `uv run attendance-agent -v` | Run with verbose/debug logging |
| `uv run attendance-agent --config path/to/config.yaml` | Use a custom config file |

You can also use `python -m src.main` instead of `uv run attendance-agent` if you prefer.

## Notifications

The agent sends desktop notifications for important events:

| Event | Notification |
|-------|-------------|
| Joined class | "Joined Class: Data Structures (staying ~120 min)" |
| Join failed | "Join Failed: Data Structures (Could not click join buttons)" |
| Class cancelled | "No Meeting Found: Data Structures. Class may be cancelled." |
| Left meeting | "Class Ended: Left meeting: Data Structures" |
| Browser crashed | "Browser Crashed: Lost connection during: Data Structures" |
| Session expired | "Session Expired: Teams login expired. Run --login" |

Set `notifications.discord_webhook_url` in config to also get alerts on your phone via Discord.

## Config Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `join_early_minutes` | 3 | Join N minutes before class start time |
| `stay_extra_minutes` | 5 | Stay N minutes after class is supposed to end |
| `max_wait_for_meeting` | 15 | Wait up to N minutes for meeting to appear |
| `poll_interval_seconds` | 15 | Check for meeting every N seconds |
| `retry_join_attempts` | 3 | Retry joining if it fails |
| `browser.headless` | false | Run browser without visible window |
| `browser.channel` | msedge | Browser to use (msedge, chromium, chrome) |
| `notifications.desktop_toast` | true | Show desktop notifications |
| `notifications.discord_webhook_url` | "" | Discord webhook for phone alerts |

## Auto-Start on Windows Login

```bash
python scripts/install_task.py          # Install scheduled task
python scripts/install_task.py --remove # Remove it
```

This creates a Windows Task Scheduler entry so the agent starts automatically when you log in.

## Project Structure

```
attendance_agent/
├── config/
│   ├── config.yaml              # Your timetable (gitignored)
│   └── config.example.yaml      # Template for new users
├── src/
│   ├── main.py                  # CLI entry point
│   ├── config_loader.py         # YAML parsing + validation
│   ├── scheduler.py             # Main-thread timetable scheduler
│   ├── browser.py               # Playwright persistent browser context
│   ├── teams_navigator.py       # Teams UI interactions
│   ├── meeting_joiner.py        # Full join lifecycle orchestrator
│   ├── selectors.py             # All CSS/aria selectors (update when Teams UI changes)
│   ├── notifier.py              # Desktop + Discord notifications
│   └── utils.py                 # Retry decorators, logging setup
├── scripts/
│   └── install_task.py          # Windows Task Scheduler auto-start
├── browser_data/                # Saved browser session (gitignored)
├── logs/                        # Rotating log files (gitignored)
├── pyproject.toml               # Project config + dependencies
├── uv.lock                     # Pinned dependency versions
└── .gitignore
```

## Troubleshooting

**"Not logged in" error**
Your session expired. Run `uv run attendance-agent --login` again.

**Meeting not detected**
The agent polls for up to 15 minutes. If the meeting starts very late, increase `max_wait_for_meeting` in config.

**Selectors not working (can't click buttons)**
Teams UI updates can break selectors. Run `uv run attendance-agent --pause` to open Playwright Inspector, find the new selectors, and update `src/selectors.py`.

**No audio in meeting**
Make sure `browser.channel` is set to `msedge` in your config. Edge has the best Teams compatibility.

**Mic not muted**
The agent tries both UI button clicks and keyboard shortcuts (Ctrl+Shift+M). If your Teams uses a different layout, update the selectors in `src/selectors.py`.

## License

MIT

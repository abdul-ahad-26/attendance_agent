# MS Teams Auto-Join Attendance Agent

A Python agent that automatically joins your MS Teams classes on schedule so your attendance is always marked. Built with Playwright browser automation.

You configure your weekly timetable once, and the agent handles everything: navigating to the right team/channel, waiting for the meeting to start, muting mic, turning off camera, joining, staying for the duration, and leaving.

## How It Works

1. **Scheduler fires** 3 minutes before class time
2. **Navigates** to the correct Team > Channel in MS Teams web
3. **Polls** for an active meeting (checks every 15 seconds, waits up to 15 minutes)
4. **Joins** the meeting with mic muted and camera off
5. **Stays** in the meeting for the class duration
6. **Leaves** automatically when the class ends
7. **Sends notifications** (desktop toast + optional Discord) on success or failure

## Quick Start

### Prerequisites

- **Python 3.8+**
- **Microsoft Edge** (pre-installed on Windows)
- **Windows** (tested on Windows 10/11 with WSL)

### 1. Clone and install

Using **uv** (recommended):

```bash
git clone <repo-url>
cd attendance_agent
uv venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
playwright install msedge
```

Using **pip** (alternative):

```bash
git clone <repo-url>
cd attendance_agent
pip install -r requirements.txt
playwright install msedge
```

### 2. Configure your timetable

```bash
cp config/config.example.yaml config/config.yaml
```

Edit `config/config.yaml` with your details:

```yaml
student:
  email: "your.email@university.edu"

timetable:
  - name: "Data Structures (Mon)"
    day: "Monday"
    time: "09:00"
    duration_minutes: 120
    team: "Your Team Name"        # Exact name from MS Teams
    channel: "General"            # Exact channel name

  - name: "Algorithms (Tue)"
    day: "Tuesday"
    time: "14:00"
    duration_minutes: 90
    team: "Your Team Name"
    channel: "Algorithms"
```

> **Your `config.yaml` is gitignored** — it never gets pushed. Your email and timetable stay private.

### 3. Login (one-time)

```bash
python -m src.main --login
```

This opens Edge and navigates to Teams. Log in manually. Your session is saved in `browser_data/` and persists across runs — you only need to do this once.

### 4. Test with a class

```bash
python -m src.main --join-now "Data Structures (Mon)"
```

Use the exact class `name` from your config. This immediately tries to join that class (useful for testing during a live meeting).

### 5. Start the agent

```bash
python -m src.main
```

This starts the scheduler. It runs in the foreground and auto-joins classes at the times in your timetable. Leave it running.

## All Commands

| Command | Description |
|---------|-------------|
| `python -m src.main --login` | One-time browser login (saves session) |
| `python -m src.main --join-now "Class Name"` | Immediately join a specific class |
| `python -m src.main --pause` | Open Playwright Inspector to discover/debug selectors |
| `python -m src.main` | Start the scheduled auto-join agent |
| `python -m src.main -v` | Run with verbose/debug logging |
| `python -m src.main --config path/to/config.yaml` | Use a custom config file |

## Auto-Start on Windows Login

```bash
python scripts/install_task.py          # Install scheduled task
python scripts/install_task.py --remove # Remove it
```

This creates a Windows Task Scheduler entry so the agent starts automatically when you log in.

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

## Project Structure

```
attendance_agent/
├── config/
│   ├── config.yaml              # Your timetable (gitignored)
│   └── config.example.yaml      # Template for new users
├── src/
│   ├── main.py                  # CLI entry point
│   ├── config_loader.py         # YAML parsing + validation
│   ├── scheduler.py             # APScheduler timetable scheduler
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
├── requirements.txt
└── .gitignore
```

## Troubleshooting

**"Not logged in" error**
Your session expired. Run `python -m src.main --login` again.

**Meeting not detected**
The agent polls for up to 15 minutes. If the meeting starts very late, increase `max_wait_for_meeting` in config.

**Selectors not working (can't click buttons)**
Teams UI updates can break selectors. Run `python -m src.main --pause` to open Playwright Inspector, find the new selectors, and update `src/selectors.py`.

**No audio in meeting**
Make sure `browser.channel` is set to `msedge` in your config. Edge has the best Teams compatibility.

**Mic not muted**
The agent tries both UI button clicks and keyboard shortcuts (Ctrl+Shift+M). If your Teams uses a different layout, update the selectors in `src/selectors.py`.

## Dependencies

```
playwright==1.49.0        # Browser automation
apscheduler==3.10.4       # Timetable scheduling
pyyaml==6.0.2             # Config parsing
plyer==2.1.0              # Desktop notifications
```

## License

MIT

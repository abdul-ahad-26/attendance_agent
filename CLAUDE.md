# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the agent (normal operation)
uv run attendance-agent

# One-time login to save Teams session
uv run attendance-agent --login

# Immediately join a specific class by name (for testing)
uv run attendance-agent --join-now "Research Methodology (Fri)"

# Verbose/debug logging
uv run attendance-agent --verbose

# Open Playwright Inspector to discover new selectors
uv run attendance-agent --pause
```

There are no tests. Install dependencies via `uv sync`, then install Playwright browsers with `uv run playwright install msedge`.

## Architecture

The agent is single-threaded (required by Playwright's sync API). All components run on the main thread.

### Data flow

```
config.yaml → config_loader.py → Config/ClassEntry/Settings
                                        ↓
main.py (mode_scheduler) → scheduler.py (run_scheduler loop, 30s tick)
                                        ↓ join_callback
                           meeting_joiner.py (MeetingJoiner.join_class)
                                        ↓
                           teams_navigator.py (Playwright page interactions)
                                        ↓
                           browser.py (BrowserManager, CDP connection)
```

### Key design decisions

**Browser lifecycle (`src/browser.py`):** Edge is launched as an independent subprocess with `--remote-debugging-port=9222`, then connected to via Playwright's `connect_over_cdp`. This means `Ctrl+C` stops the Python process but leaves the browser and any active meeting running. On next start, `BrowserManager.start()` checks port 9222 first and reconnects to the existing window. The persistent profile is stored in `browser_data/`.

**Scheduler (`src/scheduler.py`):** Runs a `while True` loop checking every 30 seconds. Tracks joined classes as `(name, date)` pairs in `joined_today` to avoid double-joining. On startup it immediately joins any class currently in progress. Passes `leave_by` (next class start time) to `join_class` so back-to-back classes leave 2 minutes before the next one starts.

**Join flow (`src/meeting_joiner.py`):** Five steps — navigate to channel → poll for meeting button (up to `max_wait_for_meeting` minutes) → click Join → mute mic + turn off camera on pre-join screen → click Join now → verify in meeting → click mic button again to ensure muted → stay until class end → leave.

**Selectors (`src/selectors.py`):** All CSS/aria selectors are centralised here. Teams UI changes frequently — this is the first place to update when joins break. Each selector is a list of alternatives tried in order.

**Teams URL:** Teams redirects from `teams.microsoft.com` to `teams.cloud.microsoft`. Both domains are recognised as valid Teams URLs throughout the code.

### Configuration

Copy `config/config.example.yaml` → `config/config.yaml`. The only required change is `student.email`. Timetable entries require `name`, `day` (lowercase), `time` (HH:MM), `duration_minutes`, `team`, and `channel` — `team`/`channel` must match the exact names visible in Teams.

### Notifications

`Notifier` sends desktop toasts (via `plyer`) and/or Discord webhook embeds. Both are optional and controlled by `settings.notifications` in config.

"""All CSS and aria selectors for MS Teams web UI.

Every UI interaction references selectors from this file.
Each selector is a list of alternatives tried in order (first match wins).
Update these when Teams UI changes.

Note: New Teams (2024+) uses data-cid attributes. Old Teams used data-tid.
Both are included for compatibility.
"""

# ---------------------------------------------------------------------------
# Teams left sidebar / app bar
# ---------------------------------------------------------------------------
TEAMS_APP_BAR_TEAMS_BUTTON = [
    '[data-tid="app-bar-Teams"]',
    '[data-cid="app-bar-Teams"]',
    'button[aria-label="Teams"]',
    'button:has-text("Teams")',
]

# ---------------------------------------------------------------------------
# Team list (left panel after clicking Teams tab)
# ---------------------------------------------------------------------------


def team_item(team_name: str) -> list:
    """Selectors to find a specific team in the team list."""
    return [
        f'[data-tid="team-{team_name}-li"]',
        f'div.team-name:has-text("{team_name}")',
        f'[aria-label*="{team_name}"]',
        f'text="{team_name}"',
    ]


def channel_item(channel_name: str) -> list:
    """Selectors to find a specific channel under an expanded team."""
    return [
        f'[data-tid="channel-{channel_name}-li"]',
        f'a[aria-label*="{channel_name}"]',
        f'[data-cid] >> text="{channel_name}"',
        f'span:has-text("{channel_name}")',
    ]


# ---------------------------------------------------------------------------
# Meeting banner / join button inside a channel
# ---------------------------------------------------------------------------
MEETING_JOIN_BUTTON = [
    '[data-tid="join-btn"]',
    '[data-cid="join-btn"]',
    'button[aria-label*="Join"]',
    'button:has-text("Join")',
]

# Indicates an active/ongoing meeting in the channel header area
ACTIVE_MEETING_INDICATOR = [
    '[data-tid="meeting-active-indicator"]',
    '[data-cid="meeting-active-indicator"]',
    '[data-tid="join-btn"]',
    '[data-cid="join-btn"]',
    'div:has-text("Meeting started")',
    'button:has-text("Join")',
]

# ---------------------------------------------------------------------------
# Pre-join screen (mic/camera toggles + "Join now" button)
# ---------------------------------------------------------------------------
MIC_TOGGLE = [
    '[data-cid="calling-pre-join-mic-button"]',
    '[data-tid="toggle-mute"]',
    '[data-tid="prejoin-audio-toggle"]',
    'button[aria-label*="Mic"]',
    'button[aria-label*="Mute"]',
    'button[aria-label*="microphone"]',
    '#microphone-toggle',
]

CAMERA_TOGGLE = [
    '[data-cid="calling-pre-join-camera-button"]',
    '[data-tid="toggle-video"]',
    '[data-tid="prejoin-video-toggle"]',
    'button[aria-label*="Camera"]',
    'button[aria-label*="video"]',
    '#video-toggle',
]

JOIN_NOW_BUTTON = [
    '[data-cid="calling-pre-join-join-button"]',
    '[data-tid="prejoin-join-button"]',
    'button:has-text("Join now")',
    'button[aria-label="Join now"]',
]

# ---------------------------------------------------------------------------
# In-meeting controls
# ---------------------------------------------------------------------------
HANGUP_BUTTON = [
    '[data-cid="calling-hangup-button"]',
    '[data-tid="hangup-btn"]',
    'button[aria-label="Leave"]',
    'button[aria-label*="Hang up"]',
    '#hangup-button',
]

# Used to verify we are still in a meeting
IN_MEETING_INDICATOR = [
    '[data-cid="calling-hangup-button"]',
    '[data-tid="calling-roster"]',
    '[data-tid="hangup-btn"]',
    'button[aria-label="Leave"]',
    'button[aria-label*="Hang up"]',
]

# ---------------------------------------------------------------------------
# Session / login state
# ---------------------------------------------------------------------------
LOGGED_IN_INDICATOR = [
    '[data-tid="app-bar-Teams"]',
    '[data-cid="app-bar-Teams"]',
    'button[aria-label="Teams"]',
    '#app-bar-Teams',
]

LOGIN_EMAIL_INPUT = [
    'input[type="email"]',
    'input[name="loginfmt"]',
]

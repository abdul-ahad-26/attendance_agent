"""All CSS and aria selectors for MS Teams web UI (new Teams on teams.cloud.microsoft).

Every UI interaction references selectors from this file.
Each selector is a list of alternatives tried in order (first match wins).
Update these when Teams UI changes.

Selectors discovered from the live Teams UI (March 2026).
"""

# ---------------------------------------------------------------------------
# Teams left sidebar / app bar (vertical icon bar on the far left)
# ---------------------------------------------------------------------------
TEAMS_APP_BAR_TEAMS_BUTTON = [
    'button:has-text("Teams")',
    '[data-tid="app-bar-Teams"]',
    '[aria-label="Teams"]',
]

# ---------------------------------------------------------------------------
# Team list (left panel after clicking Teams tab)
# ---------------------------------------------------------------------------


def team_item(team_name: str) -> list:
    """Selectors to find a specific team in the team list."""
    return [
        f'[aria-label*="{team_name}"]',
        f'text="{team_name}"',
    ]


def channel_item(channel_name: str) -> list:
    """Selectors to find a specific channel under an expanded team."""
    return [
        f'a[aria-label*="{channel_name}"]',
        f'[data-tid*="channel"] >> text="{channel_name}"',
        f'text="{channel_name}"',
    ]


# ---------------------------------------------------------------------------
# Meeting banner / join button inside a channel
# The Join button is a blue button on the meeting card in the channel posts.
# ---------------------------------------------------------------------------
MEETING_JOIN_BUTTON = [
    'button:has-text("Join")',
    '[data-tid="join-btn"]',
    'button[aria-label*="Join"]',
]

# Indicates an active/ongoing meeting in the channel
ACTIVE_MEETING_INDICATOR = [
    'button:has-text("Join")',
    '[data-tid="join-btn"]',
]

# ---------------------------------------------------------------------------
# Pre-join screen (mic/camera toggles + "Join now" button)
# ---------------------------------------------------------------------------
MIC_TOGGLE = [
    'button[aria-label*="Mic"]',
    'button[aria-label*="Mute"]',
    'button[aria-label*="microphone"]',
    '[data-tid="toggle-mute"]',
    '[data-cid="calling-pre-join-mic-button"]',
]

CAMERA_TOGGLE = [
    'button[aria-label*="Camera"]',
    'button[aria-label*="Video"]',
    'button[aria-label*="video"]',
    '[data-tid="toggle-video"]',
    '[data-cid="calling-pre-join-camera-button"]',
]

JOIN_NOW_BUTTON = [
    'button:has-text("Join now")',
    'button[aria-label="Join now"]',
    '[data-tid="prejoin-join-button"]',
    '[data-cid="calling-pre-join-join-button"]',
]

# ---------------------------------------------------------------------------
# In-meeting controls
# ---------------------------------------------------------------------------
IN_MEETING_MIC_TOGGLE = [
    'button[aria-label="Mute"]',
    'button[aria-label="Unmute"]',
    'button[aria-label*="mute"]',
    'button[aria-label*="Mute"]',
    '[data-tid="toggle-mute"]',
    '[data-cid="calling-mute-button"]',
]

HANGUP_BUTTON = [
    'button[aria-label="Leave"]',
    'button[aria-label*="Hang up"]',
    'button:has-text("Leave")',
    '[data-tid="hangup-btn"]',
    '[data-cid="calling-hangup-button"]',
]

# Used to verify we are still in a meeting
IN_MEETING_INDICATOR = [
    'button[aria-label="Leave"]',
    'button[aria-label*="Hang up"]',
    '[data-tid="hangup-btn"]',
    '[data-cid="calling-hangup-button"]',
]

# ---------------------------------------------------------------------------
# Session / login state
# ---------------------------------------------------------------------------
LOGGED_IN_INDICATOR = [
    'button:has-text("Teams")',
    '[data-tid="app-bar-Teams"]',
]

LOGIN_EMAIL_INPUT = [
    'input[type="email"]',
    'input[name="loginfmt"]',
]

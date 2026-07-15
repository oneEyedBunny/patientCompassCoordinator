# Central color palette — mirrors .streamlit/config.toml.
# Update here; both apps reflect the change automatically.

# Streamlit theme (must stay in sync with .streamlit/config.toml)
PRIMARY = "#0066CC"
BG      = "#FFFFFF"
SURFACE = "#F0F2F6"
TEXT    = "#262730"

# Shared UI
HEADER_BG = "#E2E8F0"       # table and section header background

# Chat app — teal accent, indigo buttons
CHAT_ACCENT    = "#0d9488"  # title, chat borders
CHAT_BTN       = "#4f46e5"  # primary button
CHAT_BTN_HOVER = "#4338ca"  # primary button hover

# Dashboard
DASH_SELECT_BG = "#f0f6ff"  # selectbox selection highlight

# Latency thresholds — adjusted for multi-tool agentic flows on free-tier Groq
LATENCY_GOOD_S     = 15        # ≤ 15s → green
LATENCY_WARN_S     = 35        # 15–35s → orange, > 35s → red
LATENCY_COLOR_GOOD = "#2e7d32"
LATENCY_COLOR_WARN = "#e65100"
LATENCY_COLOR_BAD  = "#c62828"

"""RisingWave brand tokens, CSS, and Plotly theming."""

import streamlit as st

# Brand colors
BRAND_BLUE = "#005EEC"
BRAND_BLUE_LIGHT = "#337EF0"
BRAND_GREEN = "#62F4C0"
BG_DARK = "#081F29"
BG_ELEVATED = "#0A3246"
BG_CARD = "#0C2535"
TEXT_MUTED = "#A0A0AB"
TEXT_DIM = "#70707B"
BORDER_DARK = "rgba(255,255,255,0.1)"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
ERROR = "#EF4444"

# URLs
RW_LOGO = "https://www.risingwave.com/_next/static/media/risingwave-logo-white-text.86234334.svg"
RW_ICON = "https://www.risingwave.com/metadata/icon.svg"
RW_URL = "https://www.risingwave.com"
RW_DOCS = "https://docs.risingwave.com"
RW_GITHUB = "https://github.com/risingwavelabs/risingwave"
RW_CLOUD = "https://cloud.risingwave.com"

# Chart palette
STAGE_COLORS = {
    "received": BRAND_BLUE, "picking": WARNING, "packed": "#8B5CF6",
    "shipped": BRAND_GREEN, "delay": ERROR,
    "Pending": BRAND_BLUE, "Picking": WARNING, "Packed": "#8B5CF6",
    "Shipped": BRAND_GREEN, "Delayed": ERROR,
}


def inject_css():
    st.markdown(f"""
    <style>
        /* ── Fade-in animation for all refreshing elements ── */
        @keyframes fadeIn {{
            from {{ opacity: 0.4; }}
            to {{ opacity: 1; }}
        }}

        /* Apply fade-in to fragment content on refresh */
        div[data-testid="stMetric"],
        div[data-testid="stDataFrame"],
        .stPlotlyChart {{
            animation: fadeIn 0.5s ease-in-out;
        }}

        /* ── Brand styling ── */
        header[data-testid="stHeader"] {{ background-color: {BG_DARK}; }}
        div[data-testid="stMetric"] {{
            background: {BG_CARD}; border: 1px solid {BORDER_DARK};
            border-radius: 8px; padding: 12px 16px;
        }}
        div[data-testid="stMetric"] label {{
            color: {TEXT_MUTED}; font-size: 0.75rem;
            text-transform: uppercase; letter-spacing: 0.05em;
        }}
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
            color: #FFFFFF; font-size: 1.8rem;
        }}
        h3 {{ color: {BRAND_GREEN} !important; font-size: 1rem !important;
             text-transform: uppercase; letter-spacing: 0.08em; }}
        div[data-testid="stDataFrame"] {{
            border: 1px solid {BORDER_DARK}; border-radius: 8px;
        }}
        section[data-testid="stSidebar"] {{
            background-color: {BG_CARD}; border-right: 1px solid {BORDER_DARK};
        }}
        .stPlotlyChart {{
            border: 1px solid {BORDER_DARK}; border-radius: 8px; overflow: hidden;
        }}
    </style>
    """, unsafe_allow_html=True)


def apply_rw_layout(fig, height=350):
    fig.update_layout(
        height=height,
        margin=dict(t=10, b=30, l=40, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT_MUTED, size=12),
        xaxis=dict(gridcolor=BORDER_DARK, zerolinecolor=BORDER_DARK),
        yaxis=dict(gridcolor=BORDER_DARK, zerolinecolor=BORDER_DARK),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_MUTED)),
        # Keep chart identity stable across data updates — Plotly animates
        # the data change instead of recreating the chart from scratch
        uirevision="stable",
        transition={"duration": 400, "easing": "cubic-in-out"},
    )
    return fig

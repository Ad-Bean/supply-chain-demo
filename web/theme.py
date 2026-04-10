"""RisingWave brand tokens and Plotly theming (framework-agnostic)."""

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
}


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
        transition={"duration": 500, "easing": "cubic-in-out"},
    )
    return fig

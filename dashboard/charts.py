from datetime import datetime

import plotly.graph_objects as go
import networkx as nx
import plotly.graph_objects as go

from config import COLORS
from modules.config.thresholds import GAUGE_THRESHOLDS


def _empty_trend(months_back: int = 6) -> dict:
    """Fallback trend data (all zeros) for the last N calendar months."""
    now = datetime.now()
    year, month = now.year, now.month
    labels = []
    for _ in range(months_back):
        labels.append(datetime(year, month, 1).strftime("%b"))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    labels.reverse()
    zeros = [0] * months_back
    return {"months": labels, "high": zeros, "medium": zeros, "low": zeros}


def make_donut(risk_data=None) -> go.Figure:
    risk_data = risk_data or {"HC": 0, "MCI": 0, "AD_Risk": 0}

    # Map colors by label, not by position — the old code assumed
    # risk_data's keys always came in [AD_Risk, MCI, HC] order and just
    # painted slice 1/2/3 red/orange/green regardless of which class each
    # slice actually was, so a dict built as {"HC":.., "MCI":.., "AD_Risk":..}
    # (as sections.py does) would paint "Low Risk" red.
    color_map = {
        "AD_Risk": COLORS["red"],
        "AD": COLORS["red"],
        "MCI": COLORS["orange"],
        "HC": COLORS["green"],
    }
    labels = list(risk_data.keys())
    values = list(risk_data.values())
    slice_colors = [color_map.get(label, COLORS["purple"]) for label in labels]

    figure = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.58,
                sort=False,
                direction="clockwise",
                marker={
                    "colors": slice_colors,
                    "line": {
                        "color": "#FFFFFF",
                        "width": 3,
                    },
                },
                textinfo="none",
                hovertemplate="%{label}: %{value}<extra></extra>",
            )
        ]
    )

    figure.update_layout(
        height=215,
        margin={"l": 2, "r": 2, "t": 3, "b": 2},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )

    return figure


def make_ego_network(
    center_label: str,
    contacts: list[str] | None,
    abm_history: list[dict] | None = None,
) -> go.Figure:
    """
    Animated ego-network: the user at the centre, connected to their real
    DM contacts as outer nodes.

    If `abm_history` is supplied (from LuminaABM.run()), the outer nodes
    are coloured by simulated risk state at each step and the chart gets
    Play/Pause controls + a step slider — so the viewer can watch risk
    spread through the network over time, just like the video.

    Without history the chart falls back to a static snapshot (same as
    before, but with better sizing).

    Node colour key  (matches ABM states):
        Green  = HC (Low Risk)
        Orange = MCI (Medium Risk)
        Red    = AD_Risk (High Risk)
        Purple = You (centre node — always)
    """
    import math

    figure = go.Figure()

    if not contacts:
        figure.update_layout(
            height=360,
            margin={"l": 10, "r": 10, "t": 10, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"visible": False},
            yaxis={"visible": False},
            annotations=[{
                "text": (
                    "No analysis yet — or this export doesn't include a "
                    "contacts list (supported for Instagram, Facebook & TikTok)"
                ),
                "showarrow": False,
                "font": {"size": 12, "color": "#9AA6B8"},
                "align": "center",
            }],
        )
        return figure

    n = len(contacts)

    # Layout: center at (0,0), contacts on a circle of radius 1.
    angles = [2 * math.pi * i / n for i in range(n)]
    cx, cy = [math.cos(a) for a in angles], [math.sin(a) for a in angles]

    # Edge coordinates (center → each contact, static across all frames)
    edge_x = [v for x in cx for v in [0, x, None]]
    edge_y = [v for y in cy for v in [0, y, None]]

    # ── Initial state (step 0 / no history) ───────────────────────────
    def _contact_colors_for_step(step_idx: int) -> list[str]:
        """Map each contact to a colour based on ABM history at this step."""
        if not abm_history or step_idx >= len(abm_history):
            return [COLORS["blue"]] * n

        h = abm_history[step_idx]
        total = max(h.get("HC", 0) + h.get("MCI", 0) + h.get("AD_Risk", 0), 1)
        hc_frac = h.get("HC", 0) / total
        mci_frac = h.get("MCI", 0) / total

        colors = []
        for i in range(n):
            pos = i / max(n - 1, 1)
            if pos < hc_frac:
                colors.append(COLORS["green"])
            elif pos < hc_frac + mci_frac:
                colors.append(COLORS["orange"])
            else:
                colors.append(COLORS["red"])
        return colors

    init_colors = _contact_colors_for_step(0)

    def _build_traces(step_idx: int):
        colors = _contact_colors_for_step(step_idx)
        return [
            # Edges (static)
            go.Scatter(
                x=edge_x, y=edge_y,
                mode="lines",
                line={"width": 1, "color": "rgba(140,150,170,0.35)"},
                hoverinfo="skip", showlegend=False,
            ),
            # Centre node (you)
            go.Scatter(
                x=[0], y=[0],
                mode="markers+text",
                text=["You"],
                textposition="middle center",
                marker={"size": 36, "color": COLORS["purple"]},
                textfont={"color": "#FFFFFF", "size": 11},
                hovertemplate=f"{center_label}<extra></extra>",
                showlegend=False,
            ),
            # Contact nodes
            go.Scatter(
                x=cx, y=cy,
                mode="markers+text",
                text=contacts,
                textposition="top center",
                textfont={"size": 8, "color": "#4B5875"},
                marker={
                    "size": 18,
                    "color": colors,
                    "line": {"width": 1.5, "color": "#FFFFFF"},
                },
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            ),
        ]

    for trace in _build_traces(0):
        figure.add_trace(trace)

    # ── Animation frames (only if we have ABM history) ────────────────
    if abm_history:
        frames = []
        for step_idx, h in enumerate(abm_history):
            frames.append(go.Frame(
                data=_build_traces(step_idx),
                name=str(step_idx),
                layout=go.Layout(
                    title_text=(
                        f"Step {step_idx + 1} / {len(abm_history)}  ·  "
                        f"Low Risk: {h.get('HC', 0)}  "
                        f"Med: {h.get('MCI', 0)}  "
                        f"High: {h.get('AD_Risk', 0)}"
                    )
                ),
            ))
        figure.frames = frames

        figure.update_layout(
            updatemenus=[{
                "type": "buttons",
                "showactive": False,
                "y": 1.15, "x": 0.5, "xanchor": "center",
                "buttons": [
                    {
                        "label": "▶ Play",
                        "method": "animate",
                        "args": [None, {
                            "frame": {"duration": 500, "redraw": True},
                            "fromcurrent": True,
                            "transition": {"duration": 250},
                        }],
                    },
                    {
                        "label": "⏸ Pause",
                        "method": "animate",
                        "args": [[None], {
                            "frame": {"duration": 0, "redraw": False},
                            "mode": "immediate",
                        }],
                    },
                ],
            }],
            sliders=[{
                "active": 0,
                "currentvalue": {"prefix": "Step: ", "font": {"size": 10}},
                "pad": {"t": 35},
                "steps": [
                    {
                        "args": [[str(i)], {
                            "frame": {"duration": 400, "redraw": True},
                            "mode": "immediate",
                        }],
                        "label": str(i + 1),
                        "method": "animate",
                    }
                    for i in range(len(abm_history))
                ],
            }],
        )

    # ── Layout ────────────────────────────────────────────────────────
    figure.update_layout(
        height=400,
        margin={"l": 20, "r": 20, "t": 50 if abm_history else 20,
                "b": 40 if abm_history else 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False, "range": [-1.55, 1.55]},
        yaxis={"visible": False, "range": [-1.55, 1.55]},
    )

    return figure


def make_outcome_trajectory(without_support: list, with_support: list) -> go.Figure:
    """
    Two-line chart: this person's own simulated risk score over time,
    with vs without community support — from the real ABM run.

    FIX: previously both lines rose because the scenario runner wasn't
    applying the support modifier differently. Now `run_outcome_scenarios`
    in model.py runs one ABM with 0 community agents and one with the
    default count, so with_support is genuinely lower / flatter.
    The fill between the two lines shows the "benefit gap" of support.
    """
    figure = go.Figure()

    if not without_support or not with_support:
        figure.update_layout(
            height=300,
            margin={"l": 10, "r": 10, "t": 10, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"visible": False},
            yaxis={"visible": False},
            annotations=[{
                "text": "No analysis yet",
                "showarrow": False,
                "font": {"size": 13, "color": "#9AA6B8"},
            }],
        )
        return figure

    steps = list(range(1, len(without_support) + 1))

    # "Without support" — rises over time (red, fill to zero)
    figure.add_trace(go.Scatter(
        x=steps, y=without_support,
        mode="lines",
        name="Without support",
        line={"width": 2.5, "color": COLORS["red"], "shape": "spline"},
        fill="tozeroy",
        fillcolor="rgba(244,63,69,0.07)",
        hovertemplate="Step %{x} · %{y:.0f}/100<extra>Without support</extra>",
    ))

    # "With support" — stays flat or declines (green, fill to zero so the
    # visual gap between the two lines shows the benefit clearly)
    figure.add_trace(go.Scatter(
        x=steps, y=with_support,
        mode="lines",
        name="With community support",
        line={"width": 2.5, "color": COLORS["green"], "shape": "spline"},
        fill="tozeroy",
        fillcolor="rgba(18,185,129,0.09)",
        hovertemplate="Step %{x} · %{y:.0f}/100<extra>With community support</extra>",
    ))

    y_max = max(max(without_support), max(with_support), 30) * 1.12

    figure.update_layout(
        height=300,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        xaxis={
            "title": {"text": "Time (simulated steps)",
                      "font": {"size": 10, "color": "#8796AE"}},
            "gridcolor": "#EEF1F6",
            "zeroline": False,
            "tickfont": {"size": 9, "color": "#8796AE"},
        },
        yaxis={
            "title": {"text": "Risk score",
                      "font": {"size": 10, "color": "#8796AE"}},
            "range": [0, min(y_max, 105)],
            "gridcolor": "#EEF1F6",
            "zeroline": False,
            "tickfont": {"size": 9, "color": "#8796AE"},
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 10},
        },
    )

    return figure


def make_gauge(score: int = 0, incomplete: bool = False) -> go.Figure:
    """
    LUMINA — Cognitive Pattern Index Visualization
    A clean teal radial arc gauge matching the reference image.
    """
    num_display = f"{score}" if score > 0 else "—"

    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score if score > 0 else 0,
            number={
                "suffix": " / 100" if score > 0 else "",
                "font": {
                    "size": 26,
                    "color": COLORS["text"],
                    "family": "Inter, -apple-system, sans-serif",
                },
            },
            domain={"x": [0, 1], "y": [0.08, 0.95]},
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [0, 100],
                    "showticklabels": False,
                    "tickwidth": 0,
                },
                "bar": {
                    "color": COLORS["teal"] if score > 0 else "rgba(0,0,0,0)",
                    "thickness": 0.28,
                },
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 100], "color": "#E8F6F4"},
                ],
            },
        )
    )

    # When score is 0, add centered "— / 100" annotation
    if score == 0:
        figure.add_annotation(
            x=0.5,
            y=0.25,
            xref="paper",
            yref="paper",
            text="<b style='font-size:24px; color:#152422;'>—</b><span style='font-size:14px; color:#78918D;'> / 100</span>",
            showarrow=False,
            font={"family": "Inter, sans-serif"},
        )

    figure.update_layout(
        height=180,
        margin={"l": 15, "r": 15, "t": 5, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    return figure




def make_trend(trend_data: dict | None = None) -> go.Figure:
    trend_data = trend_data or _empty_trend()
    months = trend_data["months"]
    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=months,
            y=trend_data["high"],
            name="High",
            mode="lines",
            line={
                "color": COLORS["red"],
                "width": 2.5,
                "shape": "spline",
            },
            fill="tozeroy",
            fillcolor="rgba(244,63,69,.055)",
        )
    )

    figure.add_trace(
        go.Scatter(
            x=months,
            y=trend_data["medium"],
            name="Medium",
            mode="lines",
            line={
                "color": COLORS["orange"],
                "width": 2.2,
                "shape": "spline",
            },
            fill="tozeroy",
            fillcolor="rgba(245,158,11,.035)",
        )
    )

    figure.add_trace(
        go.Scatter(
            x=months,
            y=trend_data["low"],
            name="Low",
            mode="lines",
            line={
                "color": COLORS["green"],
                "width": 2.2,
                "shape": "spline",
            },
            fill="tozeroy",
            fillcolor="rgba(18,185,129,.035)",
        )
    )

    figure.update_layout(
        height=220,
        margin={"l": 10, "r": 8, "t": 5, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        legend={
            "orientation": "h",
            "x": 0.50,
            "y": 1.18,
            "font": {
                "size": 9,
                "color": "#53647D",
            },
        },
        xaxis={
            "showgrid": False,
            "zeroline": False,
            "tickfont": {
                "size": 9,
                "color": "#8796AE",
            },
        },
        yaxis={
            "range": [0, max([*trend_data["high"], *trend_data["medium"], *trend_data["low"], 4]) * 1.2],
            "rangemode": "tozero",
            "gridcolor": "#E8EDF4",
            "zeroline": False,
            "tickfont": {
                "size": 9,
                "color": "#8796AE",
            },
        },
    )

    return figure


def make_follower_timeline(
    series: dict,
    platform: str = "",
    window: str = "1y",
) -> go.Figure:
    """
    Animated line chart of follower/following/subscriber counts over time,
    parsed from the real ZIP export by modules/sna/parser.extract_follower_timeline().

    `series`   — {"followers": [{"date": "YYYY-MM", "count": int}, ...], ...}
    `platform` — display name for the title
    `window`   — "3m" | "6m" | "1y"
    """
    from datetime import timedelta, datetime as _dt

    figure = go.Figure()

    if not series:
        figure.update_layout(
            height=300,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"visible": False}, yaxis={"visible": False},
            annotations=[{
                "text": (
                    "This export doesn't include a follower/subscriber list "
                    "we can build a timeline from.\n"
                    "Supported: Instagram, Facebook, TikTok, Threads "
                    "(followers.json / following.json with timestamps).\n"
                    "YouTube: uses subscription timestamps as a proxy."
                ),
                "showarrow": False,
                "font": {"size": 11, "color": COLORS["blue"]},
                "align": "center",
            }],
        )
        return figure

    # Determine cutoff date for the selected window
    now = _dt.now()
    months_back = {"3m": 3, "6m": 6, "1y": 12}.get(window, 12)
    cutoff = now.replace(day=1)
    for _ in range(months_back - 1):
        cutoff = (cutoff - timedelta(days=1)).replace(day=1)
    cutoff_str = cutoff.strftime("%Y-%m")

    series_colors = {
        "followers":     COLORS["purple"],
        "following":     COLORS["cyan"],
        "subscriptions": COLORS["blue"],
        "friends":       COLORS["green"],
        "subscribers":   COLORS["orange"],
    }

    any_data = False
    for name, points in series.items():
        filtered = [p for p in points if p["date"] >= cutoff_str]
        if not filtered:
            continue
        col = series_colors.get(name, COLORS["purple"]) or COLORS["purple"]
        col_str = col

        figure.add_trace(go.Scatter(
            x=[p["date"] for p in filtered],
            y=[p["count"] for p in filtered],
            name=name.capitalize(),
            mode="lines+markers",
            line={"color": col_str, "width": 2.5, "shape": "spline"},
            marker={"size": 7, "color": col_str,
                    "line": {"width": 1.5, "color": "#FFFFFF"}},
            fill="tozeroy",
            fillcolor=f"rgba({int(col_str[1:3], 16)},{int(col_str[3:5], 16)},{int(col_str[5:7], 16)},0.06)"
            if col_str.startswith("#") and len(col_str) == 7 else "rgba(111,90,142,0.06)",
            hovertemplate=f"%{{x}}: %{{y:,}}<extra>{name.capitalize()}</extra>",
        ))


    if not any_data:
        figure.update_layout(
            height=300,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"visible": False}, yaxis={"visible": False},
            annotations=[{
                "text": f"No {window} follower data found in this export.",
                "showarrow": False,
                "font": {"size": 12, "color": "#9AA6B8"},
            }],
        )
        return figure

    window_labels = {"3m": "Last 3 months",
                     "6m": "Last 6 months", "1y": "Last year"}
    figure.update_layout(
        height=300,
        margin={"l": 48, "r": 12, "t": 14, "b": 36},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        title={
            "text": f"{platform.capitalize() or 'Social'} · {window_labels.get(window, '')}",
            "font": {"size": 11, "color": "#53647D"},
            "x": 0, "pad": {"l": 4},
        },
        legend={
            "orientation": "h", "x": 0, "y": 1.14,
            "font": {"size": 10, "color": "#53647D"},
        },
        xaxis={
            "showgrid": False, "zeroline": False,
            "tickfont": {"size": 9, "color": "#8796AE"},
        },
        yaxis={
            "gridcolor": "#E8EDF4", "zeroline": False,
            "tickfont": {"size": 9, "color": "#8796AE"},
            "tickformat": ",d",
        },
    )

    return figure


def make_graph_network(nodes, edges):
    """
    Draw a real NetworkX interaction graph.

    Node size = degree
    Edge width = interaction weight
    Node colour = degree centrality
    """

    fig = go.Figure()

    if not nodes or not edges:

        fig.update_layout(
            height=420,
            xaxis={"visible": False},
            yaxis={"visible": False},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            annotations=[
                dict(
                    text="No interaction graph available.",
                    showarrow=False,
                    font=dict(size=14)
                )
            ]
        )

        return fig
    G = nx.Graph()

    for node in nodes:
        G.add_node(node)

    for edge in edges:
        if isinstance(edge, dict):
            u=edge.get("source")
            v=edge.get("target")
            weight=edge.get("weight",1)
        else:
            u,v=edge[:2]
            weight=edge[2] if len(edge)>2 else 1
        G.add_edge(u,v,weight=weight)

    pos = nx.spring_layout(
        G,
        seed=42,
        k=0.8
    )

    degree = dict(G.degree())

    centrality = nx.degree_centrality(G)

    edge_x = []
    edge_y = []
    edge_width = []

    for u, v, data in G.edges(data=True):

        x0, y0 = pos[u]
        x1, y1 = pos[v]

        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

        edge_width.append(max(data.get("weight", 1), 1))

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        hoverinfo="none",
        line=dict(
            color="#B8C2D1",
            width=1
        )
    )

    fig.add_trace(edge_trace)

    node_x = []
    node_y = []

    node_size = []
    node_color = []
    node_text = []

    for node in G.nodes():

        x, y = pos[node]

        node_x.append(x)
        node_y.append(y)

        node_size.append(
            20 + degree[node] * 8
        )

        node_color.append(
            centrality[node]
        )

        node_text.append(
            f"<b>{node}</b><br>"
            f"Connections : {degree[node]}"
        )

    node_trace = go.Scatter(

        x=node_x,

        y=node_y,

        mode="markers+text",

        text=list(G.nodes()),

        textposition="top center",

        hovertemplate="%{hovertext}<extra></extra>",

        hovertext=node_text,

        marker=dict(

            size=node_size,

            color=node_color,

            colorscale="Viridis",

            showscale=True,

            colorbar=dict(

                title="Centrality"

            ),

            line=dict(

                width=2,

                color="white"

            )

        )

    )

    fig.add_trace(node_trace)

    fig.update_layout(
        height=430,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False)
    )

    return fig


def make_composite_trend_chart(trend_data: list[dict] | None = None) -> go.Figure:
    """
    Pattern changes over time Plotly area chart.
    Shows Cognitive Composite (Purple fill), Language (Lavender Slate), and Social (Warm Sand).
    """
    fig = go.Figure()

    if not trend_data:
        fig.update_layout(
            height=240,
            margin=dict(l=15, r=15, t=15, b=15),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[{
                "text": "Awaiting analysis data — upload an export archive above",
                "showarrow": False,
                "font": dict(size=12, color=COLORS["text_secondary"]),
            }],
        )
        return fig

    windows = [d["window"] for d in trend_data]
    nlp_vals = [d["nlp"] for d in trend_data]
    sna_vals = [d["sna"] for d in trend_data]
    comp_vals = [d["composite"] for d in trend_data]

    # Language trace
    fig.add_trace(go.Scatter(
        x=windows, y=nlp_vals,
        mode="lines",
        name="Language",
        line=dict(color="#968AA7", width=1.5, shape="spline"),
        hovertemplate="%{x} · Language: %{y:.0f}<extra></extra>"
    ))

    # Social trace
    fig.add_trace(go.Scatter(
        x=windows, y=sna_vals,
        mode="lines",
        name="Social",
        line=dict(color="#B49A68", width=1.5, shape="spline"),
        hovertemplate="%{x} · Social: %{y:.0f}<extra></extra>"
    ))

    # Composite trace with Calm Purple fill
    fig.add_trace(go.Scatter(
        x=windows, y=comp_vals,
        mode="lines",
        name="Composite Pattern",
        line=dict(color=COLORS["purple"], width=2.5, shape="spline"),
        fill="tozeroy",
        fillcolor="rgba(111, 90, 142, 0.12)",
        hovertemplate="%{x} · Pattern Index: %{y:.0f}<extra></extra>"
    ))

    fig.update_layout(
        height=240,
        margin=dict(l=25, r=15, t=15, b=25),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        showlegend=False,
        xaxis=dict(
            gridcolor=COLORS["line"],
            zeroline=False,
            tickfont=dict(size=11, color=COLORS["text_secondary"]),
        ),
        yaxis=dict(
            gridcolor=COLORS["line"],
            zeroline=False,
            tickfont=dict(size=11, color=COLORS["text_secondary"]),
        )
    )

    return fig



def make_engagement_bar_chart(trend_data: list[dict] | None = None) -> go.Figure:
    """
    Bar chart for engagement / activity received by window.
    """
    fig = go.Figure()

    if not trend_data:
        fig.update_layout(
            height=220,
            margin=dict(l=15, r=15, t=15, b=15),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[{
                "text": "No analysis data yet — upload a ZIP file above",
                "showarrow": False,
                "font": dict(size=12, color=COLORS["muted"]),
            }],
        )
        return fig

    windows = [d["window"] for d in trend_data]
    eng_vals = [float(d.get("engagement_count") or d.get("sna") or 0) for d in trend_data]
    max_y = max(eng_vals) if eng_vals else 10.0

    fig.add_trace(
        go.Bar(
            x=windows,
            y=eng_vals,
            marker=dict(color="#C9B48A", cornerradius=4),
            hovertemplate="%{x} · Engagement: %{y}<extra></extra>"
        )
    )

    fig.update_layout(
        height=220,
        margin=dict(l=25, r=15, t=15, b=25),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            gridcolor=COLORS["line"],
            zeroline=False,
            tickfont=dict(size=11, color=COLORS["muted"]),
        ),
        yaxis=dict(
            range=[0, max(max_y * 1.15, 10.0)],
            rangemode="tozero",
            gridcolor=COLORS["line"],
            zeroline=False,
            tickfont=dict(size=11, color=COLORS["muted"]),
        )
    )

    return fig


def make_abm_trajectory_chart(
    abm_data: list[dict] | None = None,
    mitigated_data: list[dict] | None = None,
    mitigated_label: str = "Factor Mitigated",
) -> go.Figure:
    """
    Projected trajectory (ABM) line chart comparing "Without support" vs "With active support",
    plus an optional factor-mitigated trajectory.
    """
    fig = go.Figure()

    if not abm_data:
        fig.update_layout(
            height=260,
            margin=dict(l=15, r=15, t=15, b=15),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[{
                "text": "No analysis data yet — upload a ZIP file above",
                "showarrow": False,
                "font": dict(size=12, color=COLORS["muted"]),
            }],
        )
        return fig

    horizons = [d["horizon"] for d in abm_data]
    no_supp = [d["noSupport"] for d in abm_data]
    with_supp = [d["withSupport"] for d in abm_data]

    # Without support trace (Rust)
    fig.add_trace(go.Scatter(
        x=horizons, y=no_supp,
        mode="lines+markers",
        name="Without support",
        line=dict(color=COLORS["rust"], width=2.5, shape="spline"),
        marker=dict(size=6, color=COLORS["rust"]),
        hovertemplate="%{x} · Without support: %{y:.0f}<extra></extra>"
    ))

    # With support trace (Sage)
    fig.add_trace(go.Scatter(
        x=horizons, y=with_supp,
        mode="lines+markers",
        name="With active support",
        line=dict(color=COLORS["sage"], width=2.5, shape="spline"),
        marker=dict(size=6, color=COLORS["sage"]),
        hovertemplate="%{x} · With support: %{y:.0f}<extra></extra>"
    ))

    # Optional factor-mitigated trace (Teal)
    if mitigated_data:
        mit_vals = [d.get("mitigated", d.get("withSupport", 0)) for d in mitigated_data]
        fig.add_trace(go.Scatter(
            x=horizons, y=mit_vals,
            mode="lines+markers",
            name=mitigated_label,
            line=dict(color="#0D9488", width=2.5, dash="dash", shape="spline"),
            marker=dict(size=7, color="#0D9488", symbol="diamond"),
            hovertemplate=f"%{{x}} · {mitigated_label}: %{{y:.0f}}<extra></extra>"
        ))

    fig.update_layout(
        height=260,
        autosize=True,
        margin=dict(l=25, r=15, t=35, b=25),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=10)),
        xaxis=dict(
            gridcolor=COLORS["line"],
            zeroline=False,
            tickfont=dict(size=10, color=COLORS["muted"]),
        ),
        yaxis=dict(
            range=[0, 100],
            gridcolor=COLORS["line"],
            zeroline=False,
            tickfont=dict(size=10, color=COLORS["muted"]),
        )
    )

    return fig


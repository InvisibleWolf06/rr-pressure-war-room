"""SupeRR Selector S2 · Round 1 — Pressure Reliability War Room (Rajasthan Royals)
Run: streamlit run app.py
"""
import json
import re
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="RR Pressure War Room", page_icon="🏏", layout="wide")
DATA = Path(__file__).parent / "data"
PINK, BLUE, NAVY, GOLD, GREY = "#E4007C", "#254AA5", "#0B1E4A", "#F2B705", "#8A93A6"


@st.cache_data
def load():
    d = json.loads((DATA / "dashboard_data.json").read_text())
    w = json.loads((DATA / "worms.json").read_text())
    return d, w


D, W = load()
V = D["validation"]
RR = D["rr"]

st.markdown(f"""
<style>
.block-container {{padding-top: 1.4rem;}}
.hero {{background: linear-gradient(110deg,{NAVY} 0%,{BLUE} 60%,{PINK} 100%); color:#fff; padding:22px 26px; border-radius:16px; margin-bottom:14px}}
.hero h1 {{margin:0; font-size:1.9rem; color:#fff}} .hero p {{margin:6px 0 0; opacity:.9}}
.card {{border:1px solid #E3E6EE; border-radius:14px; padding:14px 16px; margin-bottom:10px; background:#fff}}
.card h4 {{margin:0 0 4px 0}} .muted {{color:{GREY}; font-size:.85rem}}
.rank {{display:inline-block; min-width:30px; height:30px; line-height:30px; text-align:center; border-radius:8px; background:{PINK}; color:#fff; font-weight:700; margin-right:8px}}
.chip {{display:inline-block; padding:2px 9px; border-radius:999px; font-size:.75rem; margin:2px 4px 2px 0; background:#EEF1F8; color:{NAVY}}}
.chip.rr {{background:{PINK}; color:#fff}} .chip.warn {{background:#FFF4D6; color:#7A5600}}
.moment {{border-left:5px solid {PINK}; background:#FAFBFE; padding:10px 14px; border-radius:8px; margin-bottom:8px}}
.moment.bad {{border-left-color:{GREY}}}
.big {{font-size:1.6rem; font-weight:700; color:{NAVY}}}
</style>""", unsafe_allow_html=True)

st.markdown("""<div class="hero"><h1>🏏 Pressure Reliability War Room</h1>
<p>Who delivers when the game is on the line — measured ball by ball, judged moment by moment, adjusted for flat IPL pitches,
and built into a <b>varied</b> auction board for Rajasthan Royals.</p></div>""", unsafe_allow_html=True)

tabs = st.tabs(["🏆 War Room", "⚡ Pressure Moments", "🔬 Player Lab", "🩷 RR Fit", "📐 Method & Proof", "📋 Full Leaderboard"])


def fmt_band(c):
    return f"model rank {c['raw_rank']} · 80% band {c['rank_band'][0]}–{c['rank_band'][1]} · P(top-10) {c['p_top10']:.0f}%"


def chips(c, kind):
    out = [f"<span class='chip'>{c['role']}</span>", f"<span class='chip'>{c['nationality']}</span>"]
    if kind == "bat":
        out.append(f"<span class='chip'>{c['hand']}</span>")
    out.append(f"<span class='chip'>IPL: {c['ipl_team']}</span>" if c['ipl_seasons'] else "<span class='chip warn'>IPL-untested</span>")
    if c["in_rr"]:
        out.append("<span class='chip rr'>Already RR</span>")
    return "".join(out)


def headline(c, kind):
    p = c["pressure"]
    if kind == "bat":
        return (f"Under pressure: <b>SR {p['sr']}</b> vs {p['xsr']} expected · avg {p['avg']} · "
                f"dots {p['dot']}% vs {p['xdot']}% · {c['moment_stats']['won']}/{c['moment_stats']['n']} pressure moments won")
    return (f"Under pressure: <b>econ {p['econ']}</b> vs {p['xecon']} expected · ball/wkt {p['bpw']} · "
            f"dots {p['dot']}% vs {p['xdot']}% · {c['moment_stats']['won']}/{c['moment_stats']['n']} pressure overs won")


# ---------------------------------------------------------------- WAR ROOM
with tabs[0]:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Balls modelled", "195,124", "867 matches · IPL + T20I 2022–26")
    k2.metric("Pressure balls", "Top 20% leverage", "56% fall outside the death overs")
    k3.metric("Batting: holds across eras", f"{V['bat']['temporal_prr']:.2f}", f"raw clutch score: {V['bat']['temporal_naive']:.2f}")
    k4.metric("Bowling: holds across eras", f"{V['bowl']['temporal_prr']:.2f}", f"raw clutch score: {V['bowl']['temporal_naive']:.2f}")
    st.caption("Repeatability = correlation of a player's score in odd-numbered vs even-numbered matches. A score that doesn't repeat is luck, not skill.")

    cb, cw = st.columns(2)
    for col, key, kind, title in [(cb, "bat_top", "bat", "Top 10 batters under pressure"), (cw, "bowl_top", "bowl", "Top 10 bowlers under pressure")]:
        with col:
            st.subheader(title)
            for c in D[key]:
                st.markdown(f"""<div class="card"><h4><span class="rank">{c['rank']}</span>{c['name']}
                <span style="float:right" class="big">{c['prr']}</span></h4>
                {chips(c, kind)}<div class="muted" style="margin-top:6px">{headline(c, kind)}</div>
                <div class="muted">{fmt_band(c)}</div></div>""", unsafe_allow_html=True)

    st.subheader("RR auction board")
    AVL = {"available": "In auction pool", "rumoured": "Release rumoured", "contracted": "Under contract", "rr": "RR player", "retired": "Retired", "ineligible": "Not eligible"}
    st.markdown("The ranking above is the model's own order. This board answers who RR can actually buy at the IPL 2027 mini-auction (Goa, 16 Dec): RR's own players, "
                "IPL retirees, players not eligible for the auction and players under contract elsewhere are taken out first. The rest go in rating order, skipping one only "
                "when he would break a cap or leave too few places for a role the squad needs.")
    st.info("Built from the official IPL 2027 retention lists of 17 November 2026 (trades included). Players released that day are back in the auction pool.")
    st.info("The Match Simulator, Player Lab strengths maps, Scouting & Auction plan and Retain & Release tabs live in the stadium version of this dashboard (app_stadium.py).")
    v1, v2 = st.columns(2)
    for col, key, exk, rules in [(v1, "bat_board", "bat_excluded", "buyable only · ≤3 openers · ≥2 No.3–4 · ≥3 middle order or finisher · ≥2 left-handers · ≤4 IPL-untested · model rank ≤80"),
                                 (v2, "bowl_board", "bowl_excluded", "buyable only · ≥3 death bowlers · ≥2 new-ball · ≥2 wrist spin · ≥1 finger spin · ≥2 left-arm · ≤5 spinners · ≤4 IPL-untested · model rank ≤80")]:
        with col:
            st.dataframe(pd.DataFrame([{"#": c["rank"], "Player": c["name"], "Model rank": c["raw_rank"], "Role": c["role"], "PRR": c["prr"], "Status": AVL.get(c.get("avail"), "")} for c in D[key]]),
                         hide_index=True, width='stretch')
            st.caption("Rules: " + rules)
            for e in D[exk]:
                st.markdown(f"- **{e['name']}** not on the board: {e['reason']}")

# ---------------------------------------------------------------- MOMENTS
def worm_fig(mid, pid, kind, title, team):
    w = W[str(mid)]
    mine = [i for i, (s_, b_) in enumerate(zip(w["striker"], w["bowler"])) if (s_ if kind == "bat" else b_) == pid]
    inn_p = w["inn"][mine[0]] if mine else 1
    # player's team batted in innings inn_p (batter) or in the other innings (bowler)
    team_bats_first = (inn_p == 1) if kind == "bat" else (inn_p == 2)
    y = [(v if team_bats_first else 1 - v) * 100 for v in w["p1"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=w["x"], y=y, mode="lines", line=dict(color=BLUE, width=2),
                             name=f"{team} win %", text=w["label"], hovertemplate="%{text}<br>Win %{y:.0f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=[w["x"][i] for i in mine], y=[y[i] for i in mine], mode="markers",
                             marker=dict(color=PINK, size=8), name="Balls he faced" if kind == "bat" else "Balls he bowled",
                             text=[w["label"][i] for i in mine], hovertemplate="%{text}<br>Win %{y:.0f}%<extra></extra>"))
    fig.add_vline(x=20, line_dash="dot", line_color=GREY)
    fig.add_hline(y=50, line_color="#E3E6EE")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10), title=title, yaxis=dict(range=[0, 100], title=f"{team} win %"),
                      xaxis=dict(title="Overs (0–20 first innings · 20–40 second innings)"), legend=dict(orientation="h", y=-0.25), plot_bgcolor="#fff")
    return fig


with tabs[1]:
    st.markdown("Every rating here is backed by **real match situations**. Pick a player to replay the moments that define him — "
                "and the one that went wrong. The line is his team's win probability after every ball; pink dots are the balls he faced or bowled.")
    kind = st.radio("Discipline", ["Batters", "Bowlers"], horizontal=True, key="mk")
    kd = "bat" if kind == "Batters" else "bowl"
    cards = D["bat_cards"] if kd == "bat" else D["bowl_cards"]
    order = sorted(cards.values(), key=lambda c: c["raw_rank"])
    top_ids = [c["id"] for c in D[kd + "_top"]]
    names = [f"{'★ ' if c['id'] in top_ids else ''}{c['name']} (model #{c['raw_rank']})" for c in order]
    pick = st.selectbox("Player", names, key="mp")
    c = order[names.index(pick)]
    st.markdown(f"### {c['name']}  ·  PRR {c['prr']}")
    st.markdown(chips(c, kd) + f"<div class='muted' style='margin-top:6px'>{headline(c, kd)}</div>", unsafe_allow_html=True)
    allm = [("Signature", m) for m in c["moments"]] + [("Blemish", m) for m in c["blemish"]]
    for tag, m in allm:
        cls = "moment bad" if tag == "Blemish" else "moment"
        ko = " · <b>KNOCKOUT</b>" if m.get("ko") else ""
        st.markdown(f"""<div class="{cls}"><b>{tag}</b> · {m['date']} · {m['comp']} vs {m['opp']}{ko}<br>
        <b>Walked into:</b> {m['situation']}<br><b>Did:</b> {m['did']}<br>
        <b>Win probability:</b> {m['wp']} · credited swing <b>{m['wpa']:+.1f} pts</b> · {m['result']}</div>""", unsafe_allow_html=True)
    opts = [f"{t}: {m['date']} vs {m['opp']}" for t, m in allm]
    sel = st.selectbox("Replay a moment", opts)
    t, m = allm[opts.index(sel)]
    if m.get("match_id"):
        mt = re.match(r"(.+?) \d+/\d+", m["situation"])
        my_team = (mt.group(1) if mt else "His team") if kd == "bat" else f"His team (bowling vs {m['opp']})"
        st.plotly_chart(worm_fig(m["match_id"], c["id"], kd, m["result"], my_team), width='stretch')
    st.caption("Credited swing adds up the win-probability change on every ball he faced (or bowled) from the moment pressure began. "
               "It can exceed the start-to-finish change when team-mates lost ground at the other end.")

# ---------------------------------------------------------------- PLAYER LAB
def bar_vs(labels, actual, expected, title, better_low=False):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=expected, name="Expected (same situation, same pitch)", marker_color="#C9CFDD"))
    fig.add_trace(go.Bar(x=labels, y=actual, name="Actual", marker_color=PINK))
    fig.update_layout(barmode="group", height=300, margin=dict(l=10, r=10, t=40, b=10), title=title,
                      legend=dict(orientation="h", y=-0.25), plot_bgcolor="#fff")
    return fig


with tabs[2]:
    kind = st.radio("Discipline", ["Batters", "Bowlers"], horizontal=True, key="lk")
    kd = "bat" if kind == "Batters" else "bowl"
    cards = D["bat_cards"] if kd == "bat" else D["bowl_cards"]
    order = sorted(cards.values(), key=lambda c: c["raw_rank"])
    nm = [c["name"] for c in order]
    a, b2 = st.columns(2)
    p1 = a.selectbox("Player", nm, key="l1")
    p2 = b2.selectbox("Compare with", ["—"] + nm, key="l2")
    sel = [order[nm.index(p1)]] + ([order[nm.index(p2)]] if p2 != "—" else [])

    comp_lbl = {"b_runs": "Runs above expected", "b_out": "Dismissal avoidance", "b_dot": "Dot avoidance",
                "w_runs": "Runs saved", "w_wkt": "Wickets above expected", "w_dot": "Dot-ball creation",
                "moment": "Moments won", "delta": "Rise vs own baseline"}
    fig = go.Figure()
    for i, c in enumerate(sel):
        ks = list(c["components"].keys())
        fig.add_trace(go.Scatterpolar(r=[c["components"][k] for k in ks] + [c["components"][ks[0]]],
                                      theta=[comp_lbl[k] for k in ks] + [comp_lbl[ks[0]]], fill="toself",
                                      name=c["name"], line_color=[PINK, BLUE][i], opacity=.7))
    fig.update_layout(height=380, polar=dict(radialaxis=dict(range=[-3, 3.5])), margin=dict(l=30, r=30, t=30, b=30),
                      title="PRR components (z-scores vs eligible players)")
    st.plotly_chart(fig, width='stretch')

    for c in sel:
        st.markdown(f"#### {c['name']}")
        x1, x2 = st.columns(2)
        s = c["splits"]
        if kd == "bat":
            with x1:
                st.plotly_chart(bar_vs(["All pressure", "vs spin", "Death overs", "In IPL"],
                                       [c["pressure"]["sr"], s["vs_spin"][0], s["death"][0], s["ipl"][0]],
                                       [c["pressure"]["xsr"], s["vs_spin"][1], s["death"][1], s["ipl"][1]],
                                       "Strike rate under pressure vs expected"), width='stretch')
                st.caption(f"Pressure balls: all {c['pressure']['balls']} · vs spin {s['vs_spin'][2]} · death {s['death'][2]} · IPL {s['ipl'][2]}")
            with x2:
                sq = c["squeeze"]
                st.markdown(f"**Squeeze response** (ball after 3+ dots, {sq['n']} times): scores {sq['score']}% · out {sq['out']}%")
                st.markdown(f"**Decision vs execution** under pressure: decision {c['decision']:+.2f} · execution {c['execution']:+.2f}  \n"
                            "<span class='muted'>Decision = value of the shot he chose vs the average shot to that ball type in that phase. "
                            "Execution = what happened vs what that shot usually yields. Units: milli-WP per leverage-unit.</span>", unsafe_allow_html=True)
        else:
            with x1:
                st.plotly_chart(bar_vs(["All pressure", "Death overs", "Middle overs", "In IPL"],
                                       [c["pressure"]["econ"], s["death"][0], s["middle"][0], s["ipl"][0]],
                                       [c["pressure"]["xecon"], s["death"][1], s["middle"][1], s["ipl"][1]],
                                       "Economy under pressure vs expected (lower is better)"), width='stretch')
                st.caption(f"Pressure balls: all {c['pressure']['balls']} · death {s['death'][2]} · middle {s['middle'][2]} · IPL {s['ipl'][2]}")
            with x2:
                bb = c["bounce"]
                st.markdown(f"**Bounce-back** (ball after being hit for 4/6, {bb['n']} times): dot {bb['dot']}% · boundary again {bb['bdry']}%")
                st.markdown(f"**Decision vs execution** under pressure: decision {c['decision']:+.2f} · execution {c['execution']:+.2f}  \n"
                            "<span class='muted'>Decision = value of the delivery chosen vs the average delivery to that batter hand in that phase. "
                            "Execution = outcome vs that delivery's usual value.</span>", unsafe_allow_html=True)
        if c.get("dna"):
            dn = c["dna"]
            tl = [t["name"] for t in dn["top"]]
            f2 = go.Figure()
            f2.add_trace(go.Bar(y=tl, x=[t["base_share"] for t in dn["top"]], orientation="h", name="Normal situations", marker_color="#C9CFDD"))
            f2.add_trace(go.Bar(y=tl, x=[t["share"] for t in dn["top"]], orientation="h", name="Under pressure", marker_color=BLUE))
            f2.update_layout(barmode="group", height=260, margin=dict(l=10, r=10, t=40, b=10), yaxis=dict(autorange="reversed"),
                             title=f"{'Shot' if kd == 'bat' else 'Delivery'} DNA under pressure · drift {dn['drift']}",
                             xaxis_title="% of balls", legend=dict(orientation="h", y=-0.3), plot_bgcolor="#fff")
            st.plotly_chart(f2, width='stretch')
            st.caption("Drift = Jensen–Shannon divergence between his pressure and normal mix (0 = identical game plan, 1 = completely different).")

# ---------------------------------------------------------------- RR FIT
with tabs[3]:
    st.markdown(f"#### Where RR lost games under pressure (IPL 2025–26)")
    tt = pd.DataFrame(RR["team_table"]).sort_values("bat")
    f = go.Figure()
    f.add_trace(go.Bar(y=tt.team, x=tt.bat, orientation="h", name="Batting", marker_color=[PINK if t == "Rajasthan Royals" else "#C9CFDD" for t in tt.team]))
    f.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10), title="Batting: win % gained per 100 pressure balls", plot_bgcolor="#fff")
    c1, c2 = st.columns(2)
    c1.plotly_chart(f, width='stretch')
    with c2:
        sl = pd.DataFrame(RR["bat_slot"])
        ph = pd.DataFrame(RR["bowl_phase_type"])
        ph["label"] = ph["phase"] + " · " + ph["btype"]
        g = go.Figure()
        g.add_trace(go.Bar(x=sl.role_slot, y=sl.gap, marker_color=[PINK if v < 0 else BLUE for v in sl.gap], name="Batting slot",
                           text=[f"n={n}" for n in sl.n], textposition="outside"))
        g.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10), title="RR batting vs league, by slot (gap, win %/100 pressure balls)", plot_bgcolor="#fff")
        st.plotly_chart(g, width='stretch')
    h = go.Figure()
    h.add_trace(go.Bar(x=ph.label, y=ph.gap, marker_color=[PINK if v < 0 else BLUE for v in ph.gap],
                       text=[f"n={n}" for n in ph.n], textposition="outside"))
    h.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title="RR bowling vs league, by phase and type (gap)", plot_bgcolor="#fff")
    st.plotly_chart(h, width='stretch')
    cl = RR["close"]
    st.warning(f"RR won only **{cl['won']} of {cl['n']}** close IPL games in 2025–26 (decided by ≤15 runs or ≤3 wickets). "
               "The leaks: Nos. 5–7 and the tail in run chases, death-overs batting, and death-overs bowling — both pace and spin.")

    def fit_bat(c):
        s, out = c["splits"], []
        if c["role"] in ("Middle order", "Finisher"):
            out.append("Plugs RR's biggest leak: Nos. 5–7 under pressure.")
        if c["role"] == "Top order":
            out.append("No. 3–4 anchor — RR's top order sits below league average under pressure.")
        if s["death"][2] >= 30 and s["death"][0] and s["death"][0] > s["death"][1]:
            out.append(f"Death-overs pressure SR {s['death'][0]} vs {s['death'][1]} expected.")
        if s["vs_spin"][2] >= 30 and s["vs_spin"][0] and s["vs_spin"][0] > s["vs_spin"][1]:
            out.append(f"Beats spin under pressure: SR {s['vs_spin'][0]} vs {s['vs_spin'][1]} expected.")
        if c["in_rr"]:
            out.append("Already an RR player: the case for building around him.")
        if not c["ipl_seasons"]:
            out.append("IPL-untested: pressure record is from T20Is; price in the risk of adjusting to IPL conditions.")
        return out or ["Pressure-proof top-order option."]

    def fit_bowl(c):
        s, out = c["splits"], []
        if "Death" in str(c.get("phase_role")) and s["death"][2] >= 30 and s["death"][0] < s["death"][1]:
            out.append(f"Fixes RR's death-overs leak: pressure economy at the death {s['death'][0]} vs {s['death'][1]} expected.")
        if c.get("kind") != "Pace" and s["death"][2] >= 18 and s["death"][0] < s["death"][1]:
            out.append(f"A spinner who can bowl at the death ({s['death'][0]} vs {s['death'][1]} expected) — RR's death spin is −0.32 vs league.")
        if c.get("kind") != "Pace":
            out.append("Pairs with RR's middle-overs spin, already a strength, to squeeze the chase.")
        if "New ball" in str(c.get("phase_role")):
            out.append("Can take the new ball too: flexibility for the Impact Player era.")
        if c["in_rr"]:
            out.append("Already an RR player.")
        return out

    st.markdown("#### How each auction-board pick strengthens RR")
    a, b3 = st.columns(2)
    with a:
        for c in D["bat_board"]:
            st.markdown(f"**{c['rank']}. {c['name']}** ({c['role']})  \n" + "  \n".join("• " + x for x in fit_bat(c)))
    with b3:
        for c in D["bowl_board"]:
            st.markdown(f"**{c['rank']}. {c['name']}** ({c['role']})  \n" + "  \n".join("• " + x for x in fit_bowl(c)))

# ---------------------------------------------------------------- METHOD
with tabs[4]:
    st.markdown("""
#### 1 · Pressure = leverage, not overs
A **pitch-adjusted win-probability model** values every ball. *Chase:* runs needed vs expected remaining runs for the balls and wickets left on that pitch.
*Batting first:* projected total vs the venue-season par. **Leverage** for a ball is the expected win-probability swing across everything that could happen
(dot, 1, 2, 4, 6, wicket, extra), normalised so the average ball in that innings = 1. Ball pressure = leverage × 1.2 if 3+ dots in a row × 1.2 if a wicket fell in the
last 6 balls. **The top 20% of balls are pressure balls.** Close finishes contain 84% more of them than other games, and 43% of death-over balls are *low* pressure (dead games).

#### 2 · Flat-wicket correction
Every expectation uses the match's **scoring environment**: venue effect (shrunk) + competition-season run rate. IPL rose from 8.5 to 9.8 runs/over in 2022–26,
so 40 off 25 in 2026 is worth less than in 2022, and a bowler going at 8.5 in 2026 is excellent.

#### 3 · The rating (PRR)
For each process skill (runs, dismissals, dots; for bowlers: runs, wickets, dots) I measure **actual minus expected** on every ball. Expected = same innings, same ball,
wickets, required rate, pace/spin and pitch. Estimate under pressure = player's (shrunk) all-situation skill + his pressure difference × credibility n/(n+200).
Then add **moments won** (pressure innings/overs where he gained win probability) and **rise vs own baseline**. Opponent weighting: associates 0.5, Ireland/Zim 0.8, A-teams 0.75. Recency 0.55 (2022) → 1.0 (2026). Knockouts ×1.25.
""")
    wts = pd.DataFrame({"Component": ["Runs vs expected", "Dismissals / wickets", "Dots", "Moments won", "Rise vs baseline"],
                        "Batting weight": [.30, .20, .25, .15, .10], "Bowling weight": [.25, .20, .30, .15, .10]})
    st.dataframe(wts, hide_index=True)
    m1, m2 = st.columns(2)
    with m1:
        env = pd.DataFrame(D["env"])
        f = go.Figure()
        for ipl, col, nmx in [(True, PINK, "IPL"), (False, BLUE, "T20I")]:
            e = env[env.ipl == ipl]
            f.add_trace(go.Scatter(x=e.yr, y=e.actual, mode="lines+markers", name=nmx, line_color=col))
        f.update_layout(height=320, title="Flat-wicket factor: runs per over by season", yaxis_title="RPO", plot_bgcolor="#fff", margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(f, width='stretch')
    with m2:
        f = go.Figure()
        cats = ["Batting · odd/even", "Batting · 22–24→25–26", "Bowling · odd/even", "Bowling · 22–24→25–26"]
        f.add_trace(go.Bar(x=cats, y=[V["bat"]["split_half_naive"], V["bat"]["temporal_naive"], V["bowl"]["split_half_naive"], V["bowl"]["temporal_naive"]],
                           name="Naive clutch (win-prob added only)", marker_color="#C9CFDD"))
        f.add_trace(go.Bar(x=cats, y=[V["bat"]["split_half_prr"], V["bat"]["temporal_prr"], V["bowl"]["split_half_prr"], V["bowl"]["temporal_prr"]],
                           name="PRR", marker_color=PINK))
        f.update_layout(barmode="group", height=320, title="Does the score repeat? (correlation)", plot_bgcolor="#fff",
                        margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(f, width='stretch')
    st.markdown("""
#### 4 · Honest limits
- Pressure performance is **noisy**: rising above your own usual level does not repeat, so the rating mostly rewards holding a high level under pressure. Every rank carries an 80% band from 300 match-level bootstrap resamples.
- An earlier version reported odd-even repeatability of 0.35 and 0.26; a bug let the two halves overlap. Rankings were unaffected.
- First-innings win probability is less certain (AUC 0.70 vs 0.90 for chases) because the target is unknown.
- No line/length, shot direction or edge data: "decision vs execution" is built from stroke and delivery labels only.
- The ranking includes everyone. The RR auction board leaves out players RR cannot buy: Pakistani nationals (Sufiyan Muqeem is #3 among bowlers), IPL retirees, Harry Brook (IPL ban), RR's own players, and anyone another franchise retained on 17 November 2026.
- DLS-shortened and no-result games are excluded; super overs are not scored.
""")

# ---------------------------------------------------------------- LEADERBOARD
with tabs[5]:
    kind = st.radio("Discipline", ["Batters", "Bowlers"], horizontal=True, key="tk")
    t = pd.DataFrame(D["bat_table"] if kind == "Batters" else D["bowl_table"])
    roles = sorted(t.role.unique())
    f1, f2, f3 = st.columns(3)
    rsel = f1.multiselect("Role", roles, default=roles)
    natsel = f2.selectbox("Players", ["All", "Indian", "Overseas"])
    q = f3.text_input("Search name")
    t = t[t.role.isin(rsel)]
    if natsel == "Indian":
        t = t[t.nat == "India"]
    elif natsel == "Overseas":
        t = t[t.nat != "India"]
    if q:
        t = t[t.name.str.contains(q, case=False)]
    t = t.rename(columns={"prr": "PRR", "rank": "Rank", "lo": "Band low", "hi": "Band high", "p10": "P(top10)%", "eps": "Pressure moments",
                          "balls": "Pressure balls", "selected": "Top 10", "board": "RR board", "nat": "Nation", "ipl_team": "IPL 2026", "avail": "Auction status"})
    st.dataframe(t.drop(columns=["id"]), hide_index=True, width='stretch', height=600)

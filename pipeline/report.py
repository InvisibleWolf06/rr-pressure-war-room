"""Builds the methodology report PDF with charts.
Usage: python -I report.py <out_dir> <pdf_path>
"""
import sys, json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                Image, PageBreak, KeepTogether, NextPageTemplate)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUT, PDF = sys.argv[1], sys.argv[2]
FD = '/usr/share/fonts/truetype/dejavu/'
pdfmetrics.registerFont(TTFont('DV', FD + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVB', FD + 'DejaVuSans-Bold.ttf'))
pdfmetrics.registerFont(TTFont('DVI', FD + 'DejaVuSans-Oblique.ttf'))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily('DV', normal='DV', bold='DVB', italic='DVI', boldItalic='DVB')

PINK, BLUE, NAVY, GREY, LIGHT = '#E4007C', '#254AA5', '#0B1E4A', '#6B7385', '#C9CFDD'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': '#B8BECC', 'axes.labelcolor': '#333',
                     'xtick.color': '#555', 'ytick.color': '#555', 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.color': '#ECEEF3', 'grid.linewidth': .6, 'axes.axisbelow': True})

D = json.load(open(f'{OUT}/dashboard_data.json'))
W = json.load(open(f'{OUT}/worms.json'))
V = D['validation']; RR = D['rr']
b = pd.read_parquet(f'{OUT}/balls.parquet', columns=['innings', 'phase', 'hp', 'LI', 'margin_close', 'match_id'])
CH = f'{OUT}/charts'; import os; os.makedirs(CH, exist_ok=True)

def save(fig, name):
    fig.savefig(f'{CH}/{name}.png', dpi=220, bbox_inches='tight'); plt.close(fig); return f'{CH}/{name}.png'

def label_bars(ax, bars, fmt='{:.0f}%', dy=0.6):
    for r in bars:
        h = r.get_height(); ax.text(r.get_x() + r.get_width() / 2, h + dy, fmt.format(h), ha='center', va='bottom', fontsize=7.5, color='#333')

# ---- chart 1: share of pressure balls by phase & innings
sh = b.groupby(['innings', 'phase'], observed=True).hp.mean().unstack(0) * 100
fig, ax = plt.subplots(figsize=(6.4, 2.6))
x = np.arange(3); w = .36
b1 = ax.bar(x - w / 2 - .01, sh[1].values, w, color=BLUE, label='Batting first')
b2 = ax.bar(x + w / 2 + .01, sh[2].values, w, color=PINK, label='Chasing')
label_bars(ax, b1); label_bars(ax, b2)
ax.set_xticks(x, ['Powerplay (1–6)', 'Middle (7–15)', 'Death (16–20)']); ax.set_ylabel('% of balls that are pressure balls')
ax.legend(frameon=False, ncol=2, loc='upper left'); ax.set_ylim(0, 48)
c1 = save(fig, 'pressure_share')

# ---- chart 2: environment by season
env = pd.DataFrame(D['env'])
fig, ax = plt.subplots(figsize=(6.4, 2.5))
for ipl, col, nm in [(True, PINK, 'IPL'), (False, BLUE, 'T20I')]:
    e = env[env.ipl == ipl]
    ax.plot(e.yr, e.actual, color=col, lw=2, marker='o', ms=5, label=nm)
    for xx, yy in zip(e.yr, e.actual):
        ax.text(xx, yy + .07, f'{yy:.2f}', ha='center', fontsize=7.5, color='#333')
ax.set_xticks(env.yr.unique()); ax.set_ylabel('Runs per over'); ax.legend(frameon=False, loc='upper left'); ax.set_ylim(7.8, 10.3)
c2 = save(fig, 'environment')

# ---- chart 3: reliability
fig, ax = plt.subplots(figsize=(6.4, 2.6))
cats = ['Batting\nodd vs even matches', 'Batting\n2022–24 → 2025–26', 'Bowling\nodd vs even matches', 'Bowling\n2022–24 → 2025–26']
nv = [V['bat']['split_half_naive'], V['bat']['temporal_naive'], V['bowl']['split_half_naive'], V['bowl']['temporal_naive']]
pv = [V['bat']['split_half_prr'], V['bat']['temporal_prr'], V['bowl']['split_half_prr'], V['bowl']['temporal_prr']]
x = np.arange(4)
r1 = ax.bar(x - .19, nv, .36, color=LIGHT, label='Naive clutch score (win-prob added only)')
r2 = ax.bar(x + .19, pv, .36, color=PINK, label='Pressure Reliability Rating (PRR)')
for rr_ in list(r1) + list(r2):
    h = rr_.get_height(); ax.text(rr_.get_x() + rr_.get_width() / 2, max(h, 0) + .008, f'{h:.2f}', ha='center', fontsize=7.5)
ax.axhline(0, color='#999', lw=.8); ax.set_xticks(x, cats, fontsize=7.8); ax.set_ylabel('Correlation'); ax.set_ylim(-.05, .42)
ax.legend(frameon=False, fontsize=7.8, loc='upper center', bbox_to_anchor=(.5, -.28), ncol=2)
c3 = save(fig, 'reliability')

# ---- chart 4: rank bands
def bands(lst, title, name):
    fig, ax = plt.subplots(figsize=(3.2, 3.3))
    names = [c['name'] for c in lst][::-1]
    for i, c in enumerate(lst[::-1]):
        lo, hi = c['rank_band']
        ax.plot([lo, hi], [i, i], color=LIGHT, lw=4, solid_capstyle='round')
        ax.plot(c['raw_rank'], i, 'o', color=PINK, ms=6, mec='white', mew=1.2)
    ax.set_yticks(range(len(names)), names, fontsize=7.5); ax.set_xlim(0, 90); ax.set_xlabel('Model rank (dot) and 80% band', fontsize=8)
    ax.set_title(title, fontsize=9, loc='left', color=NAVY); ax.grid(axis='y', visible=False)
    return save(fig, name)
c4a = bands(D['bat_top'], 'Batters', 'bands_bat'); c4b = bands(D['bowl_top'], 'Bowlers', 'bands_bowl')

# ---- chart 5: RR gaps
sl = pd.DataFrame(RR['bat_slot']); ph = pd.DataFrame(RR['bowl_phase_type'])
fig, axs = plt.subplots(1, 2, figsize=(6.6, 2.6), gridspec_kw={'width_ratios': [1, 1.4]})
ax = axs[0]
bars = ax.bar(sl.role_slot.str.replace(' (', '\n('), sl.gap, color=[PINK if v < 0 else BLUE for v in sl.gap])
for r_, n in zip(bars, sl.n):
    h = r_.get_height(); ax.text(r_.get_x() + r_.get_width() / 2, h + (.03 if h >= 0 else -.07), f'{h:+.2f}', ha='center', fontsize=7.5)
ax.axhline(0, color='#999', lw=.8); ax.set_ylim(-.9, .95); ax.set_title('RR batting vs league, by slot', fontsize=8.5, loc='left'); ax.tick_params(axis='x', labelsize=6.8)
ax.set_ylabel('Win % per 100 pressure balls, vs league', fontsize=7.5)
ax = axs[1]
lab = (ph.phase.str.replace('Powerplay', 'PP') + '\n' + ph.btype)
bars = ax.bar(lab, ph.gap, color=[PINK if v < 0 else BLUE for v in ph.gap])
for r_, n in zip(bars, ph.n):
    h = r_.get_height(); ax.text(r_.get_x() + r_.get_width() / 2, h + (.03 if h >= 0 else -.08), f'{h:+.2f}\nn={n}', ha='center', fontsize=6.5)
ax.axhline(0, color='#999', lw=.8); ax.set_title('RR bowling vs league, by phase and type', fontsize=8.5, loc='left'); ax.tick_params(axis='x', labelsize=7)
ax.set_ylim(-.95, .5)
c5 = save(fig, 'rr_gaps')

# ---- chart 6: example worm (top batter's signature)
c0 = D['bat_top'][0]; mo = c0['moments'][0]; w = W[str(mo['match_id'])]
mine = [i for i, s in enumerate(w['striker']) if s == c0['id']]
inn_p = w['inn'][mine[0]]; y = [(v if inn_p == 1 else 1 - v) * 100 for v in w['p1']]
fig, ax = plt.subplots(figsize=(6.4, 2.4))
ax.plot(w['x'], y, color=BLUE, lw=1.6, label='Punjab Kings win %')
ax.scatter([w['x'][i] for i in mine], [y[i] for i in mine], s=14, color=PINK, zorder=3, label=f"Balls faced by {c0['name']}")
ax.axvline(20, color='#999', ls=':', lw=.8); ax.axhline(50, color='#ddd', lw=.8)
ax.set_ylim(0, 100); ax.set_xlim(0, 40); ax.set_xlabel('Overs (0–20 first innings, 20–40 chase)'); ax.set_ylabel('Win %')
ax.legend(frameon=False, ncol=2, loc='upper left', fontsize=7.5)
c6 = save(fig, 'worm_example')

# ================================================================= PDF
ss = {
    'h1': ParagraphStyle('h1', fontName='DVB', fontSize=15, leading=19, textColor=colors.HexColor(NAVY), spaceBefore=4, spaceAfter=6),
    'h2': ParagraphStyle('h2', fontName='DVB', fontSize=11, leading=14, textColor=colors.HexColor(PINK), spaceBefore=8, spaceAfter=4),
    'p': ParagraphStyle('p', fontName='DV', fontSize=8.8, leading=12.6, textColor=colors.HexColor('#222'), spaceAfter=5),
    'small': ParagraphStyle('s', fontName='DV', fontSize=7.4, leading=9.6, textColor=colors.HexColor(GREY)),
    'cell': ParagraphStyle('c', fontName='DV', fontSize=7.4, leading=9.3),
    'cellb': ParagraphStyle('cb', fontName='DVB', fontSize=7.4, leading=9.3),
    'bul': ParagraphStyle('b', fontName='DV', fontSize=8.8, leading=12.4, leftIndent=10, bulletIndent=0, spaceAfter=2),
    'cap': ParagraphStyle('cap', fontName='DVI', fontSize=7.4, leading=9.4, textColor=colors.HexColor(GREY), spaceAfter=8),
}
P = lambda t, s='p': Paragraph(t, ss[s])
def bullets(items):
    return [Paragraph(t, ss['bul'], bulletText='•') for t in items]
def img(path, width):
    from PIL import Image as PI
    w_, h_ = PI.open(path).size
    return Image(path, width=width, height=width * h_ / w_)
def tbl(rows, widths, header_bg=NAVY, zebra=True, font=7.4):
    t = Table(rows, colWidths=widths, repeatRows=1)
    st = [('FONT', (0, 0), (-1, -1), 'DV', font), ('FONT', (0, 0), (-1, 0), 'DVB', font),
          ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_bg)), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
          ('LINEBELOW', (0, 0), (-1, -1), .3, colors.HexColor('#E3E6EE'))]
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0: st.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F6F7FB')))
    t.setStyle(TableStyle(st)); return t

def on_page(cv, doc):
    cv.saveState()
    cv.setFillColor(colors.HexColor(PINK)); cv.rect(0, A4[1] - 6, A4[0], 6, fill=1, stroke=0)
    cv.setFont('DV', 7); cv.setFillColor(colors.HexColor(GREY))
    cv.drawString(18 * mm, 10 * mm, 'SupeRR Selector Season 2 · Round 1 · Pressure Reliability Rating (PRR)')
    cv.drawRightString(A4[0] - 18 * mm, 10 * mm, f'{doc.page}')
    cv.restoreState()

def on_cover(cv, doc):
    cv.saveState()
    cv.setFillColor(colors.HexColor(NAVY)); cv.rect(0, A4[1] - 92 * mm, A4[0], 92 * mm, fill=1, stroke=0)
    cv.setFillColor(colors.HexColor(PINK)); cv.rect(0, A4[1] - 95 * mm, A4[0], 3 * mm, fill=1, stroke=0)
    cv.setFillColor(colors.white); cv.setFont('DVB', 24); cv.drawString(18 * mm, A4[1] - 38 * mm, 'Who Delivers When It Matters')
    cv.setFont('DV', 12.5); cv.drawString(18 * mm, A4[1] - 48 * mm, 'A pressure-reliability system for batters and bowlers,')
    cv.drawString(18 * mm, A4[1] - 55 * mm, 'and a varied IPL 2027 auction board for Rajasthan Royals')
    cv.setFont('DV', 9); cv.setFillColor(colors.HexColor('#C9D3F0'))
    cv.drawString(18 * mm, A4[1] - 72 * mm, 'SupeRR Selector Season 2 · Round 1 methodology report')
    cv.drawString(18 * mm, A4[1] - 78 * mm, 'Data: 195,124 deliveries · 867 matches · IPL 2022–2026 and T20Is 2022–2026')
    cv.restoreState()
    on_page(cv, doc)

doc = BaseDocTemplate(PDF, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=17 * mm,
                      title='Pressure Reliability Rating — SupeRR Selector S2 Round 1', author='SupeRR Selector submission')
fr = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='f')
frc = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 92 * mm, id='fc')
doc.addPageTemplates([PageTemplate('cover', [frc], onPage=on_cover), PageTemplate('main', [fr], onPage=on_page)])
FW = doc.width
S = [NextPageTemplate('main')]

# ---------- cover: summary + rankings
S += [P('Summary', 'h1'),
      P('We rank players on how reliably they deliver in the balls that decide matches, not on reputation and not on the death overs alone. '
        'A <b>pitch-adjusted win-probability model</b> scores every one of 195,124 deliveries. <b>Pressure</b> is defined as leverage: how much the '
        'match could swing on that ball. Each player is then judged on <b>process skills under pressure</b> (runs, dismissals and dots compared with '
        'what the same situation on the same pitch normally yields), on the <b>real pressure moments</b> he won or lost, and on whether he '
        '<b>rises above his own baseline</b>. A variety rule then turns the ranking into a balanced auction board.'),
      P('Three findings shaped the system:', 'p')]
S += bullets([
    '<b>Pressure is not the same as the death overs.</b> 56% of pressure balls come before over 16, and 43% of death-over balls carry below-average leverage, usually because the game is already decided.',
    f"<b>Raw clutch numbers are mostly luck.</b> A naive score (win probability added under pressure) barely repeats between a player's odd- and even-numbered matches "
    f"(batting {V['bat']['split_half_naive']:.2f}, bowling {V['bowl']['split_half_naive']:.2f}). Our rating repeats at {V['bat']['split_half_prr']:.2f} and {V['bowl']['split_half_prr']:.2f}. "
    f"Both also carry from 2022–24 to 2025–26 (batting {V['bat']['temporal_prr']:.2f}, bowling {V['bowl']['temporal_prr']:.2f}), where the naive score is at zero.",
    '<b>Flat pitches distort everything.</b> IPL scoring rose from 8.6 to 9.8 runs per over between 2022 and 2026, so every expectation is set by the venue and season.'])
rows = [['#', 'Batter', 'Role', 'PRR', '#', 'Bowler', 'Role', 'PRR']]
for i in range(10):
    a, c = D['bat_top'][i], D['bowl_top'][i]
    rows.append([str(i + 1), a['name'], a['role'], f"{a['prr']:.1f}", str(i + 1), c['name'], c['role'].replace('Pace · ', ''), f"{c['prr']:.1f}"])
S += [Spacer(1, 4), P('Final rankings (as entered on Unstop)', 'h2'),
      tbl(rows, [6 * mm, 34 * mm, 23 * mm, 11 * mm, 6 * mm, 34 * mm, 46 * mm, 11 * mm]),
      P('PRR is scaled so the average eligible player scores 50 and one standard deviation is 10 points.', 'cap'), PageBreak()]

# ---------- 1. pressure definition
S += [P('1 · Defining pressure', 'h1'),
      P('<b>Win probability.</b> For the chasing side, we model expected remaining runs from the balls left, wickets in hand and the match\'s scoring environment, '
        'then pass the run margin (expected runs minus runs needed, divided by the spread still possible) through a logistic curve. For the side batting first, '
        'the projected total is compared with the venue-season par. Both models are smooth by design, so a single boundary moves win probability by a believable '
        'amount. Out-of-fold accuracy: chases AUC 0.90 (Brier 0.13), with predicted and actual win rates within 2 points across every decile; first innings AUC 0.70, '
        'which is lower because the target is not yet known.'),
      P('<b>Leverage.</b> For every ball we compute the expected win-probability swing over all seven outcomes (dot, 1, 2, 4, 6, wicket, extra), weighted by how often '
        'each happens in that phase and innings. We divide by the innings average, so 1.0 means a normal ball. This is the cricket version of the leverage index used '
        'in baseball analytics.'),
      P('<b>Felt pressure.</b> The scoreboard misses the squeeze, so leverage is multiplied by 1.2 after three or more consecutive dots and by 1.2 if a wicket fell in '
        'the previous six balls. <b>The top 20% of balls by this pressure index are pressure balls</b> (threshold 1.38).'),
      img(c1, FW * .86),
      P('Figure 1. Share of balls classed as pressure balls, by phase. Chases carry pressure in every phase, and batting-first pressure clusters at the death and after collapses.', 'cap'),
      P('<b>Why this definition is meaningful.</b> It separates pressure situations from ordinary ones in the way a dressing room would. Close finishes (15 runs or '
        'fewer, 3 wickets or fewer) contain 31% pressure balls against 17% in other games. A tight 12th over in a chase of 190 qualifies, while the 19th over of '
        'a game already won does not. A phase-based definition gets both of those wrong.'),
      PageBreak()]

# ---------- 2. flat wicket + performance
S += [P('2 · The flat-wicket factor', 'h1'),
      P('Each match gets a <b>scoring environment</b>: the runs-per-over level of its competition-season (IPL vs T20I) plus a venue effect, shrunk towards zero with six '
        'matches of prior weight so small venues are not over-read. Every expectation in the system (remaining runs, par score, expected runs, dots and wickets per ball) '
        'is conditioned on it. In practice this means 40 off 25 balls in IPL 2026 is worth less than the same innings in 2022, and a bowler conceding 8.5 an over in 2026 '
        'is having a good day.'),
      img(c2, FW * .86),
      P('Figure 2. Actual runs per over by season. IPL scoring rose 15% in five years, with the Impact Player era from 2023 accelerating it; T20Is stayed flat until 2026.', 'cap'),
      P('3 · Measuring performance', 'h1'),
      P('<b>Expected-outcome model.</b> Gradient-boosted models predict, for every legal ball, the expected bat runs, dismissal probability and dot probability from: innings, '
        'balls bowled, wickets lost, scoring environment, required rate relative to the environment (in chases) and pace or spin. A player\'s value on a ball is <b>actual '
        'minus expected</b>.'),
      P('<b>Baseline plus credible pressure difference.</b> For each skill we compute the player\'s average across all balls (A) and on pressure balls (H). His pressure '
        'estimate is A × n/(n+300) + (H − A) × n<sub>p</sub>/(n<sub>p</sub>+200), where n is all balls and n<sub>p</sub> is pressure balls. This follows a key test: a player\'s overall '
        'situation-adjusted skill predicted his pressure performance in other matches better than his past pressure performance did. Pressure difference is therefore credited '
        'only as far as the sample supports.'),
      P('<b>Pressure moments.</b> A batting moment is an innings in which he faced three or more pressure balls; we credit the win probability he added from the first of '
        'them to the end of his innings. A bowling moment is an over whose average pressure index is above the threshold. Moment success rate and average swing are shrunk '
        'towards the population mean (prior of 6 and 4 moments).')]
wrows = [['Component', 'Batting', 'Weight', 'Bowling', 'Weight', 'Repeatability*'],
         ['Run value', 'Runs above expected', '30%', 'Runs saved vs expected', '25%', '0.40 / 0.17'],
         ['Wicket value', 'Dismissal avoidance', '20%', 'Wickets above expected', '20%', '0.20 / 0.03'],
         ['Dot value', 'Dot-ball avoidance', '25%', 'Dot-ball creation', '30%', '0.42 / 0.24'],
         ['Moments', 'Pressure moments won', '15%', 'Pressure overs won', '15%', '0.05 / 0.04'],
         ['Rise vs self', 'Pressure minus own baseline', '10%', 'Pressure minus own baseline', '10%', '0.13 / 0.03'],
         ]
S += [tbl(wrows, [22 * mm, 38 * mm, 13 * mm, 38 * mm, 13 * mm, 24 * mm]),
      P('*Odd vs even-match correlation of each component (batting / bowling). Weights lean towards what repeats; the moments and '
        'rise-vs-self components stay in because the brief asks for match-situation evidence and comparison with usual levels, but at lower weight.', 'cap'),
      P('<b>Model choice.</b> For every prediction task we compared, with 5-fold cross-validation grouped by match, a linear model, scikit-learn histogram gradient boosting, LightGBM and CatBoost. '
        'The boosted models were within 0.4% of each other on every task (for example, remaining-runs error 22.61, 22.60 and 22.53 runs), and all beat the linear model. '
        'CatBoost was marginally most accurate but did not improve the repeatability of the final ratings, so we kept scikit-learn gradient boosting with fixed seeds.'),
      PageBreak()]

# ---------- 4. fair comparisons
S += [P('4 · Fair comparisons', 'h1')]
S += bullets([
    '<b>Eligibility.</b> Batters: at least 10 pressure moments and 60 pressure balls. Bowlers: at least 15 pressure overs and 90 pressure balls. All players must have played in 2025 or 2026. This leaves 127 batters and 120 bowlers.',
    '<b>Opposition strength.</b> Each ball is weighted by the opponent: IPL and full members 1.0, Ireland and Zimbabwe 0.8, A-teams 0.75, associates 0.5. Runs against Hong Kong do not count the same as runs against Australia.',
    '<b>IPL and T20I together.</b> Both formats feed one model, but the scoring environment is separate for each competition-season, and the dashboard shows each player\'s IPL-only pressure numbers. Batters with no IPL experience are flagged and capped at two on the board.',
    '<b>Recency.</b> 2026 = 1.0, 2025 = 0.9, 2024 = 0.8, 2023 = 0.65, 2022 = 0.55. Knockout matches × 1.25.',
    '<b>Credit allocation.</b> Batters are credited for bat runs and their own dismissal; bowlers for everything except run-outs; extras are never the batter\'s.',
    '<b>Excluded matches.</b> DLS-shortened games (25), abandoned games and no-results. Super overs are not scored.',
    '<b>Auction reality.</b> Pakistani players are rated (Sufiyan Muqeem is the model\'s #3 bowler) but left off the board because they are not available at the IPL auction.'])
S += [P('5 · Evidence for the top 10', 'h1'),
      P('Each player\'s rank is re-estimated in 300 bootstrap resamples of matches. The dot is his model rank and the bar is the 80% range. '
        'A tight bar near the top means he is reliably elite; a wide bar means the evidence is thinner.'),
      Table([[img(c4a, FW * .49), img(c4b, FW * .49)]], colWidths=[FW * .5, FW * .5]),
      P('Figure 3. Rank uncertainty for the selected players.', 'cap')]
br = [['#', 'Batter', 'Balls', 'SR (exp)', 'Avg', 'Dot% (exp)', 'Won', 'P(top10)']]
for c in D['bat_top']:
    p = c['pressure']; ms = c['moment_stats']
    br.append([c['rank'], c['name'], p['balls'], f"{p['sr']:.0f} ({p['xsr']:.0f})", f"{p['avg']:.0f}", f"{p['dot']:.0f} ({p['xdot']:.0f})", f"{ms['won']}/{ms['n']}", f"{c['p_top10']:.0f}%"])
wr = [['#', 'Bowler', 'Balls', 'Econ (exp)', 'Balls/wkt', 'Dot% (exp)', 'Won', 'P(top10)']]
for c in D['bowl_top']:
    p = c['pressure']; ms = c['moment_stats']
    wr.append([c['rank'], c['name'], p['balls'], f"{p['econ']:.2f} ({p['xecon']:.2f})", f"{p['bpw']:.0f}", f"{p['dot']:.0f} ({p['xdot']:.0f})", f"{ms['won']}/{ms['n']}", f"{c['p_top10']:.0f}%"])
cw = [7 * mm, 36 * mm, 19 * mm, 24 * mm, 14 * mm, 22 * mm, 20 * mm, 18 * mm]
S += [PageBreak(), P('Pressure-ball numbers for the selected players', 'h2'), tbl(br, cw), Spacer(1, 8), tbl(wr, cw),
      P('All figures are on pressure balls only. "Exp." is what the same situations, on the same pitches, normally produce. Moments won = pressure innings or overs in which the player added win probability.', 'cap'),
      PageBreak()]

# ---------- 6. instance evidence
S += [P('6 · The moments behind the numbers', 'h1'),
      P('Every rating can be traced back to real match situations. The figure replays the top-ranked batter\'s signature innings ball by ball; the table gives one '
        'defining moment for each selected player. The dashboard has three signature moments and one failure for each of 60+ players, each replayable.'),
      img(c6, FW * .9),
      P(f"Figure 4. {c0['name']}, {mo['comp']}, {mo['date']}: walked in at {mo['situation']}, made {mo['did'].split(' under')[0]}. Pink dots are balls he faced. "
        f"{mo['result']}.", 'cap')]
mr = [[Paragraph('<b>Player</b>', ss['cellb']), Paragraph('<b>Match</b>', ss['cellb']), Paragraph('<b>Walked into</b>', ss['cellb']),
       Paragraph('<b>Did</b>', ss['cellb']), Paragraph('<b>Win %</b>', ss['cellb'])]]
for c in D['bat_top'] + D['bowl_top']:
    m = c['moments'][0]
    mr.append([Paragraph(c['name'], ss['cell']), Paragraph(f"{m['comp']}<br/>vs {m['opp']}{' (KO)' if m.get('ko') else ''}", ss['cell']),
               Paragraph(m['situation'], ss['cell']), Paragraph(m['did'].replace(' under pressure', ''), ss['cell']), Paragraph(m['wp'].replace(' (bowling side)', ''), ss['cell'])])
S += [tbl(mr, [27 * mm, 33 * mm, 50 * mm, 40 * mm, 22 * mm], font=7.2), PageBreak()]

# ---------- 7. variety + RR fit
cl = RR['close']
S += [P('7 · From a ranking to an auction board: variety and RR fit', 'h1'),
      P('A list of the ten highest scores would include six openers, because opening batters face the most measurable pressure. An auction board needs coverage. '
        'We therefore fill the ten in rating order, skipping a player only when he would break a cap or leave too few slots for a required role. Variety never reorders '
        'the list, and no player outside the model\'s top 25 (or with under a 20% chance of being top 25) can be pulled in to fill a role.')]
vr = [['', 'Batting rules', 'Bowling rules'],
      ['Caps', '≤3 openers · ≤5 overseas · ≤2 IPL-untested', '≤5 spinners · ≤6 overseas · ≤2 IPL-untested'],
      ['Minimums', '≥2 No. 3–4 · ≥3 middle order or finisher · ≥2 left-handers', '≥3 death bowlers · ≥2 new-ball · ≥2 wrist spin · ≥1 finger spin · ≥2 left-arm'],
      ['Left out', '; '.join(f"{e['name']} ({e['reason'].split(' already')[0]})" for e in D['bat_excluded']),
       '; '.join(f"{e['name']} ({'not available at auction' if 'Pakistan' in e['reason'] else e['reason'].split(' already')[0]})" for e in D['bowl_excluded'])]]
vr = [[Paragraph(str(x), ss['cell'] if i else ss['cellb']) for x in r] for i, r in enumerate(vr)]
S += [tbl(vr, [18 * mm, 76 * mm, 78 * mm]), Spacer(1, 6),
      P('<b>Where RR lose under pressure (IPL 2025–26).</b> RR\'s batting ranked 6th of 10 on win probability gained per 100 pressure balls. Openers beat the league; '
        f"Nos. 5–7 and the tail leak badly, and death-overs batting is the worst phase. With the ball, death overs leak with both pace and spin. RR won only {cl['won']} of {cl['n']} close games."),
      img(c5, FW),
      P('Figure 5. RR minus league average, win % per 100 pressure balls. Pink = below league. Small samples labelled (powerplay spin is only 15 balls).', 'cap')]
fit = [['Pick', 'How he strengthens RR']]
def fit_txt(c, kind):
    s = c['splits']
    if kind == 'bat':
        t = []
        if c['role'] in ('Middle order', 'Finisher'): t.append("plugs RR's biggest leak, Nos. 5–7")
        if c['role'] == 'Top order': t.append('a No. 3–4 who scores above expectation under pressure')
        if c['role'] == 'Opener': t.append('opening option to pair with or cover Jaiswal / Sooryavanshi')
        if s['death'][2] >= 30 and s['death'][0] > s['death'][1]: t.append(f"death-overs pressure SR {s['death'][0]:.0f} vs {s['death'][1]:.0f} expected")
        if s['vs_spin'][2] >= 30 and s['vs_spin'][0] > s['vs_spin'][1]: t.append(f"vs spin {s['vs_spin'][0]:.0f} vs {s['vs_spin'][1]:.0f}")
        if c['in_rr']: t.append('already RR: build around him')
        if not c['ipl_seasons']: t.append('IPL-untested: price in adjustment risk')
    else:
        t = []
        if s['death'][2] >= 18 and s['death'][0] < s['death'][1]: t.append(f"death-overs pressure economy {s['death'][0]:.2f} vs {s['death'][1]:.2f} expected: targets RR's death leak")
        if c.get('kind') != 'Pace': t.append("adds to RR's middle-overs spin squeeze")
        if 'New ball' in str(c.get('phase_role')): t.append('can also take the new ball')
        if s['middle'][2] >= 30 and s['middle'][0] < s['middle'][1] and c.get('kind') == 'Pace': t.append(f"middle-overs pace option ({s['middle'][0]:.2f} vs {s['middle'][1]:.2f})")
    return '; '.join(t)
for c in D['bat_top']: fit.append([Paragraph(f"<b>{c['name']}</b> ({c['role']})", ss['cell']), Paragraph(fit_txt(c, 'bat'), ss['cell'])])
for c in D['bowl_top']: fit.append([Paragraph(f"<b>{c['name']}</b> ({c['role'].replace('Pace · ', 'Pace, ')})", ss['cell']), Paragraph(fit_txt(c, 'bowl'), ss['cell'])])
fit[0] = [Paragraph('<b>Pick</b>', ss['cellb']), Paragraph('<b>How he strengthens RR</b>', ss['cellb'])]
S += [PageBreak(), P('How each pick strengthens RR', 'h2'), tbl(fit, [55 * mm, 117 * mm]), PageBreak()]

# ---------- 8. reliability + limitations
S += [P('8 · Reliability and limitations', 'h1'),
      P('We checked consistency in two ways. <b>Split-half</b>: rate every player separately on his odd- and even-numbered matches and correlate the two scores. '
        '<b>Across eras</b>: rate on 2022–24 only and on 2025–26 only. A score that does not repeat is measuring luck.'),
      img(c3, FW * .86),
      P('Figure 6. Our rating repeats far better than a naive clutch score, which stays close to zero on both tests.', 'cap'),
      P('<b>Notable omissions, explained.</b> Pathum Nissanka (6th), Shubman Gill (7th) and Phil Salt (10th) are openers, and three higher-rated openers already fill the opener cap. '
        'Jasprit Bumrah makes the board at 9 (model rank 14): his run-saving is among the best in the pool (economy 7.75 against 9.18 expected), but he takes a pressure wicket only every 22 balls and is even better in calm phases.'), P('Limitations', 'h2')]
S += bullets([
    'Pressure performance is inherently noisy. Even the improved rating repeats at only 0.26–0.35 between halves of a player\'s matches. Rankings also move with modelling choices: reasonable alternative models (CatBoost, LightGBM, different seeds) give rank correlations of about 0.9 with this one. Treat ranks 5–10 as tiers, not exact places, and read the bands in Figure 3.',
    'First-innings win probability is less certain (AUC 0.70) because there is no target yet; batting-first pressure is identified less sharply than chase pressure.',
    'The data has stroke and delivery labels but no line, length, shot direction, edge or field placement. Shot and delivery "DNA" and the decision-vs-execution split shown in the dashboard are descriptive and are not part of the score.',
    'T20I-only players (one batter and one bowler on the board) have no IPL evidence; their pressure record may not carry over to IPL pitches and attacks.',
    'Roles are inferred from data (median entry point; share of overs by phase), so a player who changed role recently is labelled by his recent mix only if most of his balls come from it.',
    'Availability at the 2027 auction (retentions are due on 17 November 2026) is outside the data. The board ranks pressure reliability; RR would bid only on players who are released.'])
S += [PageBreak(), P('9 · Reproducibility', 'h1'),
      P('The pipeline is five Python scripts run in order on the supplied files; every number in this report and the dashboard comes from their outputs. Random seeds are fixed, so re-running the scripts reproduces every number. Runtime is under three minutes on a laptop.'),
      tbl([['Step', 'Script', 'What it does'],
           ['1', 'engine.py', 'Scoring environment, win-probability models, leverage, pressure balls, per-ball win probability added'],
           ['2', 'reliab2.py', 'Expected runs / dismissal / dot / wicket per ball; reliability tests of candidate metrics'],
           ['3', 'moments.py', 'Pressure moments, roles, nationality, shot and delivery DNA, squeeze and bounce-back'],
           ['4', 'ratings2.py', 'PRR components, weighting, bootstrap rank bands, split-half and era validation'],
           ['5', 'select.py / rr_gaps.py', 'Variety-aware top 10, RR gap analysis, dashboard data']],
          [12 * mm, 34 * mm, 126 * mm]),
      Spacer(1, 10)]

# ---------- appendix
S += [P('Appendix · Top 15 by PRR before the variety rule', 'h1')]
for key, kind in [('bat_table', 'Batters'), ('bowl_table', 'Bowlers')]:
    rows = [['Rank', 'Player', 'Role', 'Nation', 'PRR', '80% band', 'P(top10)', 'Board']]
    for r in D[key][:15]:
        rows.append([r['rank'], r['name'], r['role'].replace('Pace · ', 'Pace, '), r['nat'], f"{r['prr']:.1f}", f"{r['lo']}–{r['hi']}", f"{r['p10']:.0f}%", '✓' if r['selected'] else ''])
    S += [P(kind, 'h2'), tbl(rows, [11 * mm, 36 * mm, 46 * mm, 24 * mm, 12 * mm, 17 * mm, 15 * mm, 12 * mm], font=7)]
doc.build(S)
print('built', PDF)

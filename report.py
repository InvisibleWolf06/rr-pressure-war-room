"""Builds the methodology report PDF with charts.
Usage: python -I report.py <out_dir> <pdf_path>
"""
import sys, json, re
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
FD = '/usr/share/fonts/truetype/liberation/'
pdfmetrics.registerFont(TTFont('DV', FD + 'LiberationSans-Regular.ttf'))
pdfmetrics.registerFont(TTFont('DVB', FD + 'LiberationSans-Bold.ttf'))
pdfmetrics.registerFont(TTFont('DVI', FD + 'LiberationSans-Italic.ttf'))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily('DV', normal='DV', bold='DVB', italic='DVI', boldItalic='DVB')

PINK, BLUE, NAVY, GREY, LIGHT = '#EC008C', '#254AA5', '#1B2F7A', '#6B7385', '#D9CCD6'
DEEP, GOLD, BLUSH = '#B8006C', '#D4A017', '#FDEEF6'
CREST = f'{OUT}/charts/crest.png'
plt.rcParams.update({'font.family': 'Liberation Sans', 'font.size': 9, 'axes.edgecolor': '#1B2F7A', 'axes.labelcolor': '#1B2F7A',
                     'xtick.color': '#222', 'ytick.color': '#222', 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': False, 'axes.linewidth': .8, 'xtick.major.size': 0, 'ytick.major.size': 0,
                     'legend.fontsize': 8, 'axes.titleweight': 'bold', 'axes.titlecolor': '#1B2F7A', 'axes.titlesize': 9.5})
def clean(ax, keep_y=False):
    ax.spines['left'].set_visible(keep_y)
    if not keep_y: ax.set_yticks([]); ax.set_ylabel('')
    else: [t.set_fontweight('bold') for t in ax.get_yticklabels()]

D = json.load(open(f'{OUT}/dashboard_data.json'))
W = json.load(open(f'{OUT}/worms.json'))
V = D['validation']; RR = D['rr']
from decimal import Decimal, ROUND_HALF_UP
V = {k: {kk: (float(Decimal(str(vv)).quantize(Decimal('0.01'), ROUND_HALF_UP)) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in V.items()}
b = pd.read_parquet(f'{OUT}/balls.parquet', columns=['innings', 'phase', 'hp', 'LI', 'margin_close', 'match_id'])
CH = f'{OUT}/charts'; import os; os.makedirs(CH, exist_ok=True)

def save(fig, name):
    fig.savefig(f'{CH}/{name}.png', dpi=220, bbox_inches='tight'); plt.close(fig); return f'{CH}/{name}.png'

def label_bars(ax, bars, fmt='{:.0f}%', dy=0.6):
    for r in bars:
        h = r.get_height(); ax.text(r.get_x() + r.get_width() / 2, h + dy, fmt.format(h), ha='center', va='bottom', fontsize=8.5, color='#1a1a1a', fontweight='bold')

# ---- chart 1: share of pressure balls by phase & innings
sh = b.groupby(['innings', 'phase'], observed=True).hp.mean().unstack(0) * 100
fig, ax = plt.subplots(figsize=(6.4, 2.6))
x = np.arange(3); w = .36
b1 = ax.bar(x - w / 2 - .01, sh[1].values, w, color=BLUE, label='Batting first')
b2 = ax.bar(x + w / 2 + .01, sh[2].values, w, color=PINK, label='Chasing')
label_bars(ax, b1); label_bars(ax, b2)
ax.set_xticks(x, ['Powerplay (1–6)', 'Middle (7–15)', 'Death (16–20)']); ax.set_ylabel('% of balls that are pressure balls')
ax.legend(frameon=False, ncol=2, loc='upper left'); ax.set_ylim(0, 48); clean(ax)
c1 = save(fig, 'pressure_share')

# ---- chart 2: environment by season
env = pd.DataFrame(D['env'])
fig, ax = plt.subplots(figsize=(6.4, 2.15))
for ipl, col, nm in [(True, PINK, 'IPL'), (False, BLUE, 'T20I')]:
    e = env[env.ipl == ipl]
    ax.plot(e.yr, e.actual, color=col, lw=2, marker='o', ms=5, label=nm)
    for xx, yy in zip(e.yr, e.actual):
        ax.text(xx, yy + .08, f'{yy:.2f}', ha='center', fontsize=8, color=col, fontweight='bold')
ax.set_xticks(env.yr.unique()); ax.set_ylabel(''); ax.legend(frameon=False, loc='upper left'); ax.set_ylim(7.8, 10.3)
[t.set_fontweight('bold') for t in ax.get_xticklabels()]; clean(ax)
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
    h = rr_.get_height(); ax.text(rr_.get_x() + rr_.get_width() / 2, max(h, 0) + .008, f'{h:.2f}', ha='center', fontsize=8.5, fontweight='bold')
ax.set_xticks(x, cats, fontsize=7.8); ax.set_ylim(0, .32); clean(ax)
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
    ax.set_title(title); ax.spines['left'].set_visible(False)
    return save(fig, name)
c4a = bands(D['bat_top'], 'Batters', 'bands_bat'); c4b = bands(D['bowl_top'], 'Bowlers', 'bands_bowl')

# ---- chart 5: RR gaps
sl = pd.DataFrame(RR['bat_slot']); ph = pd.DataFrame(RR['bowl_phase_type'])
fig, axs = plt.subplots(1, 2, figsize=(6.6, 2.6), gridspec_kw={'width_ratios': [1, 1.4]})
ax = axs[0]
bars = ax.bar(['Nos 1–2', 'Nos 3–4', 'Nos 5–7', 'Nos 8–11'], sl.gap, color=[PINK if v < 0 else BLUE for v in sl.gap])
for r_, n in zip(bars, sl.n):
    h = r_.get_height(); ax.text(r_.get_x() + r_.get_width() / 2, h + (.03 if h >= 0 else -.07), f'{h:+.2f}', ha='center', fontsize=8, fontweight='bold')
ax.axhline(0, color='#1B2F7A', lw=.8); ax.set_ylim(-.9, .95); ax.set_title('RR batting vs league, by slot'); ax.tick_params(axis='x', labelsize=6.8)
ax.spines['bottom'].set_visible(False); clean(ax)
ax = axs[1]
lab = (ph.phase.str.replace('Powerplay', 'PP') + '\n' + ph.btype)
bars = ax.bar(lab, ph.gap, color=[PINK if v < 0 else BLUE for v in ph.gap])
for r_, n in zip(bars, ph.n):
    h = r_.get_height(); ax.text(r_.get_x() + r_.get_width() / 2, h + (.03 if h >= 0 else -.08), f'{h:+.2f}\nn={n}', ha='center', fontsize=7, fontweight='bold')
ax.axhline(0, color='#1B2F7A', lw=.8); ax.set_title('RR bowling vs league, by phase and type'); ax.tick_params(axis='x', labelsize=7)
ax.set_ylim(-.95, .5); ax.spines['bottom'].set_visible(False); clean(ax)
c5 = save(fig, 'rr_gaps')

# ---- chart 6: example worm (top batter's signature)
c0 = D['bat_top'][0]; mo = c0['moments'][0]; w = W[str(mo['match_id'])]
mine = [i for i, s in enumerate(w['striker']) if s == c0['id']]
inn_p = w['inn'][mine[0]]; y = [(v if inn_p == 1 else 1 - v) * 100 for v in w['p1']]
fig, ax = plt.subplots(figsize=(6.4, 2.4))
ax.plot(w['x'], y, color=BLUE, lw=1.6, label='Punjab Kings win %')
ax.scatter([w['x'][i] for i in mine], [y[i] for i in mine], s=14, color=PINK, zorder=3, label=f"Balls faced by {c0['name']}")
ax.axvline(20, color='#1B2F7A', ls=':', lw=.8); ax.axhline(50, color='#D9CCD6', lw=.8)
ax.set_ylim(0, 100); ax.set_xlim(0, 40); ax.set_xlabel('Overs (0–20 first innings, 20–40 chase)'); ax.set_ylabel('Win %')
ax.legend(frameon=False, ncol=2, loc='upper left', fontsize=7.5); ax.set_yticks([0, 50, 100], ['0%', '50%', '100%']); clean(ax, keep_y=True); ax.set_ylabel('')
c6 = save(fig, 'worm_example')

# ================================================================= PDF
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER
INK = '#1a1a1a'
ss = {
    'h1': ParagraphStyle('h1', fontName='DVB', fontSize=17, leading=21, textColor=colors.HexColor(NAVY), spaceBefore=2, spaceAfter=3),
    'tag': ParagraphStyle('tag', fontName='DVB', fontSize=10.5, leading=13.5, textColor=colors.HexColor(PINK), spaceBefore=5, spaceAfter=8),
    'h2': ParagraphStyle('h2', fontName='DVB', fontSize=10, leading=13, textColor=colors.HexColor(NAVY), alignment=TA_CENTER, spaceBefore=8, spaceAfter=2),
    'p': ParagraphStyle('p', fontName='DV', fontSize=9.2, leading=13, textColor=colors.HexColor(INK), spaceAfter=6),
    'small': ParagraphStyle('s', fontName='DV', fontSize=7.4, leading=9.6, textColor=colors.HexColor(GREY)),
    'cell': ParagraphStyle('c', fontName='DV', fontSize=7.6, leading=9.4, textColor=colors.HexColor(INK)),
    'cellb': ParagraphStyle('cb', fontName='DVB', fontSize=7.6, leading=9.4, textColor=colors.HexColor(NAVY)),
    'bul': ParagraphStyle('b', fontName='DV', fontSize=9.2, leading=12.8, leftIndent=14, bulletIndent=1, spaceAfter=4, textColor=colors.HexColor(INK),
                          bulletFontName='DV', bulletFontSize=6.5, bulletColor=colors.HexColor(NAVY)),
    'cap': ParagraphStyle('cap', fontName='DVI', fontSize=7.2, leading=9.2, textColor=colors.HexColor('#555555'), spaceAfter=9),
}
P = lambda t, s='p': Paragraph(t, ss[s])
B = lambda t: Paragraph(t, ss['bul'], bulletText='\u25A0')
HL = lambda t: f"<font color='{PINK}'><b>{t}</b></font>"
def bullets(items):
    return [B(t) for t in items]
TAGS = {
 'Summary': 'Raw clutch numbers do not last; holding a high level when the game is tight does',
 '1 · Defining pressure': 'Pressure is how far the match can swing on a ball, not which over it is bowled in',
 '2 · The flat-wicket factor': 'Every expectation is set by venue and season, so a run in 2026 is not worth a run in 2022',
 '3 · Measuring performance': 'Each player is judged against what the same situation normally produces, then against his own usual level',
 '4 · Fair comparisons': 'Sample size, opposition, recency and competition are handled explicitly',
 '5 · Evidence for the top 10': 'Every rank comes with an uncertainty band, so firm places and tiers are easy to tell apart',
 '6 · The moments behind the numbers': 'Each rating can be traced back to real match situations',
 '7 · From the ranking to an auction board for RR': 'The ranking says who performs best under pressure; the board says who RR can actually buy',
 '8 · Reliability, robustness and limitations': 'The top 10 holds up when the hand-set choices change; pressure skill itself stays noisy',
 '9 · Reproducibility': 'Every number in this report can be regenerated from the supplied data',
}
def H1(t):
    items = [Paragraph(t, ss['h1']), HRFlowable(width='100%', thickness=1.1, color=colors.HexColor(NAVY), spaceBefore=1, spaceAfter=0)]
    if t in TAGS: items.append(Paragraph(TAGS[t], ss['tag']))
    else: items.append(Spacer(1, 8))
    return KeepTogether(items)
def H2(t):
    return KeepTogether([Paragraph(t, ss['h2']), HRFlowable(width='100%', thickness=.8, color=colors.HexColor(NAVY), spaceBefore=1, spaceAfter=5)])
def img(path, width):
    from PIL import Image as PI
    w_, h_ = PI.open(path).size
    return Image(path, width=width, height=width * h_ / w_)
NUMRE = re.compile(r'^[\s(+\-–−]*[\d.,]+')
def tbl(rows, widths, header_bg=None, zebra=False, font=7.6):
    t = Table(rows, colWidths=widths, repeatRows=1)
    st = [('FONT', (0, 0), (-1, -1), 'DV', font), ('FONT', (0, 0), (-1, 0), 'DVB', font),
          ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(NAVY)), ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor(INK)),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('VALIGN', (0, 0), (-1, 0), 'BOTTOM'),
          ('TOPPADDING', (0, 0), (-1, -1), 2.6), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.6),
          ('LINEBELOW', (0, 0), (-1, 0), .9, colors.HexColor(NAVY)), ('LINEBELOW', (0, -1), (-1, -1), .6, colors.HexColor(NAVY))]
    for j in range(len(rows[0])):
        body = [r[j] for r in rows[1:] if isinstance(r[j], (str, int, float))]
        if body and j > 0 and sum(bool(NUMRE.match(str(v))) for v in body) >= .6 * len(body):
            st.append(('ALIGN', (j, 0), (j, -1), 'RIGHT'))
    t.setStyle(TableStyle(st)); return t

def on_page(cv, doc):
    cv.saveState()
    cv.setFillColor(colors.HexColor(PINK)); cv.rect(0, A4[1] - 7, A4[0], 7, fill=1, stroke=0)
    cv.setFillColor(colors.HexColor(GOLD)); cv.rect(0, A4[1] - 8.2, A4[0], 1.2, fill=1, stroke=0)
    if doc.page > 1:
        cv.drawImage(CREST, A4[0] - 18 * mm - 7.5 * mm, A4[1] - 15.5 * mm, width=7.5 * mm, height=9 * mm, mask='auto')
    cv.setStrokeColor(colors.HexColor(PINK)); cv.setLineWidth(.6); cv.line(18 * mm, 13.5 * mm, A4[0] - 18 * mm, 13.5 * mm)
    cv.setFont('DV', 7); cv.setFillColor(colors.HexColor(GREY))
    cv.drawString(18 * mm, 10 * mm, 'P Shreyas, VIT Chennai · SupeRR Selector Season 2 · Round 1 · Pressure Reliability Rating (PRR)')
    cv.setFillColor(colors.HexColor(PINK)); cv.setFont('DVB', 7.5); cv.drawRightString(A4[0] - 18 * mm, 10 * mm, f'{doc.page}')
    cv.restoreState()

def on_cover(cv, doc):
    cv.saveState()
    top, hgt = A4[1], 92 * mm
    n = 60                                             # pink gradient band
    for i in range(n):
        k = i / (n - 1)
        r = (0xF7 + (0xB8 - 0xF7) * k) / 255; g = (0x2A + (0x00 - 0x2A) * k) / 255; b = (0xA0 + (0x6C - 0xA0) * k) / 255
        cv.setFillColorRGB(r, g, b); cv.rect(0, top - hgt + (n - 1 - i) * hgt / n, A4[0], hgt / n + .5, fill=1, stroke=0)
    cv.setFillColor(colors.HexColor(BLUE)); cv.rect(0, top - hgt - 3 * mm, A4[0], 3 * mm, fill=1, stroke=0)
    cv.setFillColor(colors.HexColor(GOLD)); cv.rect(0, top - hgt - 3.9 * mm, A4[0], .9 * mm, fill=1, stroke=0)
    # soft rings behind the crest
    cv.setStrokeColorRGB(1, 1, 1); cv.setLineWidth(.8)
    for rr_, al in [(34, .20), (44, .12), (54, .07)]:
        cv.setStrokeAlpha(al); cv.circle(A4[0] - 42 * mm, top - 46 * mm, rr_ * mm, fill=0, stroke=1)
    cv.setStrokeAlpha(1)
    cv.drawImage(CREST, A4[0] - 42 * mm - 21 * mm, top - 46 * mm - 26 * mm, width=42 * mm, height=50.4 * mm, mask='auto')
    cv.setFillColor(colors.white); cv.setFont('DVB', 23); cv.drawString(18 * mm, top - 36 * mm, 'Who Delivers')
    cv.drawString(18 * mm, top - 46 * mm, 'When It Matters')
    cv.setFillColor(colors.HexColor('#FFE38A')); cv.rect(18 * mm, top - 51 * mm, 26 * mm, .8 * mm, fill=1, stroke=0)
    cv.setFillColor(colors.white); cv.setFont('DV', 11.5); cv.drawString(18 * mm, top - 59 * mm, 'A pressure-reliability system for batters and bowlers,')
    cv.drawString(18 * mm, top - 65.5 * mm, 'and a varied IPL 2027 auction board for Rajasthan Royals')
    cv.setFont('DVB', 10.5); cv.setFillColor(colors.HexColor('#FFE38A')); cv.drawString(18 * mm, top - 74.5 * mm, 'P Shreyas · VIT Chennai')
    cv.setFont('DV', 8.5); cv.setFillColor(colors.HexColor('#FFE0F0'))
    cv.drawString(18 * mm, top - 81 * mm, 'SupeRR Selector Season 2 · Round 1 methodology report')
    cv.drawString(18 * mm, top - 86 * mm, '195,124 deliveries · 867 matches · IPL and T20Is, 2022–2026')
    cv.restoreState()
    on_page(cv, doc)

doc = BaseDocTemplate(PDF, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=19 * mm, bottomMargin=17 * mm,
                      title='Pressure Reliability Rating — SupeRR Selector S2 Round 1', author='P Shreyas, VIT Chennai')
fr = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='f')
frc = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 94 * mm, id='fc')
doc.addPageTemplates([PageTemplate('cover', [frc], onPage=on_cover), PageTemplate('main', [fr], onPage=on_page)])
FW = doc.width
S = [NextPageTemplate('main')]

# ---------- cover: summary + rankings
RB = json.load(open(f'{OUT}/robust.json'))
SB, SBN, SEN, TR = RB['spearman_brown'], RB['spearman_brown_naive'], RB['sensitivity'], RB['transfer']
EPB = pd.read_csv(f'{OUT}/bat_episodes.csv').win.mean() * 100; EPW = pd.read_csv(f'{OUT}/bowl_episodes.csv').win.mean() * 100
S += [H1('Summary'),
      P('The brief asks who delivers when the game is on the line. I started where most people start, with the death overs, and the data talked me out of it. '
        f"{HL('56%')} of the balls that swing a match most come before over 16, and {HL('43%')} of death-over balls barely matter because the game is already gone."),
      P('So I built a win-probability model that knows how flat the pitch is, ran it over all 195,124 deliveries, and called a ball a pressure ball when the match '
        'could swing a lot on it. Each player is judged on his runs, dismissals and dots on those balls against what that situation on that pitch normally produces, '
        'on the pressure moments he won or lost, and on how far he rises above his own usual level.'),
      P(f"The main finding is uncomfortable, and I would rather state it than bury it. Pressure performance as a separate skill barely persists. How far a player rises "
        f"above his own usual level in one half of his matches tells you almost nothing about the other half. What does persist is the ability to hold a high level when the "
        f"game is tight. My rating carries from 2022–24 into 2025–26 (correlation {HL(format(V['bat']['temporal_prr'], '.2f'))} for batters and {HL(format(V['bowl']['temporal_prr'], '.2f'))} for bowlers), "
        f"while a raw clutch score, the win probability a player adds under pressure, does not ({HL(format(V['bat']['temporal_naive'], '.2f'))} and {HL(format(V['bowl']['temporal_naive'], '.2f'))}). "
        f"So the ranking below, in the model's own order, is of players who perform best when it matters, rather than of a mythical clutch gene. "
        f"A separate auction board for Rajasthan Royals is in section 7.")]
rows = [['#', 'Batter', 'Role', 'PRR', '#', 'Bowler', 'Role', 'PRR']]
for i in range(10):
    a, c = D['bat_top'][i], D['bowl_top'][i]
    rows.append([str(i + 1), a['name'], a['role'], f"{a['prr']:.1f}", str(i + 1), c['name'], c['role'].replace('Pace · ', ''), f"{c['prr']:.1f}"])
S += [Spacer(1, 4), H2('Final rankings (as entered on Unstop)'),
      tbl(rows, [6 * mm, 34 * mm, 23 * mm, 11 * mm, 6 * mm, 34 * mm, 46 * mm, 11 * mm]),
      P('PRR: average eligible player = 50, one standard deviation = 10.', 'cap'),
      PageBreak()]

# ---------- 1. pressure definition
S += [H1('1 · Defining pressure'),
      P('Everything hangs off win probability, so that comes first. In a chase I estimate how many runs a side normally makes from here, given balls left, wickets in hand and '
        'how the pitch is scoring. I compare that with the runs still needed, scale the gap by how much could still change, and pass it through a logistic curve. For the side '
        'batting first I compare the projected total with par for that venue and season. I kept both models deliberately smooth. My first attempt, a boosted classifier, '
        'sometimes moved win probability by more than 30 points on one boundary, which no one watching would believe. Tested on matches it had not seen, the chase model scores '
        'AUC 0.90 (Brier 0.13) and its predicted win rates sit within 2 points of the real ones in every decile. The first-innings model manages 0.70 and can be up to 7 points '
        'off in a decile, which is what you would expect when there is no target yet.'),
      P('Pressure on a ball is its leverage. I take the seven things that can happen (dot, 1, 2, 4, 6, wicket, extra), work out how far each would move win probability, and '
        'average those swings by how often each happens in that phase. Dividing by the average for that innings means a normal ball scores 1.0. Baseball analysts have used the '
        'same idea for years.'),
      P('The scoreboard does not capture everything a batter feels, so I added two things it misses. Leverage is multiplied by 1.2 after three or more dots in a row, and by '
        '1.2 again if a wicket fell in the previous six balls. The top 20% of balls on this index are my pressure balls (threshold 1.38).'),
      img(c1, FW * .86),
      P('Figure 1. Share of balls classed as pressure balls, by phase. Chases carry pressure in every phase; batting first, it clusters at the death and after collapses.', 'cap'),
      P('Does the definition pick out the right balls? Close finishes (15 runs or fewer, 3 wickets or fewer) are 31% pressure balls, against 17% in other games. A tight 12th '
        'over chasing 190 counts. The 19th over of a game that was won in the 15th does not. Defining pressure by phase gets both of those wrong.'),
      PageBreak()]

# ---------- 2. flat wicket + performance
S += [H1('2 · The flat-wicket factor'),
      P('Each match gets a scoring environment: the run rate of its competition and season (IPL and T20Is separately) plus a venue effect. The venue effect is shrunk towards '
        'zero with six matches of prior weight, otherwise a ground with four games would look like a road or a minefield by accident. Remaining runs, par scores and the '
        'expected runs, dots and wickets on each ball all depend on it. The practical effect is that 40 off 25 in IPL 2026 is worth less than the same innings in 2022, and a '
        'bowler going at 8.5 an over in 2026 has had a good day. Because the environment is set per season, it also absorbs the jump in scoring from the Impact Player rule.'),
      img(c2, FW * .86),
      P('Figure 2. Actual runs per over by season. IPL scoring rose 15% in five years and jumped when the Impact Player rule arrived in 2023; T20Is stayed flat until 2026.', 'cap'),
      H1('3 · Measuring performance'),
      P('For every legal ball, gradient-boosted models predict the bat runs, the chance of a dismissal and the chance of a dot, using the innings, balls bowled, wickets lost, '
        'scoring environment, required rate relative to that environment (in chases) and whether the bowler is pace or spin. A player\'s value on a ball is what happened minus '
        'what was expected.'),
      P('The obvious next step is to average that over each player\'s pressure balls. On its own that does not hold up, because a few dozen pressure balls are mostly noise. '
        'So each estimate starts from the player\'s usual level and moves towards his pressure numbers only as far as the sample allows. For each skill, with A his average on '
        'all balls and H his average on pressure balls, the estimate is A × n/(n+300) + (H − A) × n<sub>p</sub>/(n<sub>p</sub>+200), where n and n<sub>p</sub> count all balls '
        'and pressure balls. The (H − A) term is the comparison with usual level the brief asks for; it also gets its own 10% component.'),
      P('I also score moments, because a rating nobody can trace back to a match is hard to trust. A batting moment is an innings with three or more pressure balls; the batter '
        f"gets the win probability he added from the first of them until he is out or the innings ends. A bowling moment is an over whose average pressure is above the threshold. "
        f"The share of moments a player wins is also my measure of consistency: the average batter wins {EPB:.0f}% of his and the average bowler {EPW:.0f}%.")]
wrows = [['Component', 'Batting', 'Weight', 'Bowling', 'Weight', 'Repeatability*'],
         ['Run value', 'Runs above expected', '30%', 'Runs saved vs expected', '25%', '0.29 / 0.26'],
         ['Wicket value', 'Dismissal avoidance', '20%', 'Wickets above expected', '20%', '0.21 / 0.00'],
         ['Dot value', 'Dot-ball avoidance', '25%', 'Dot-ball creation', '30%', '0.48 / 0.24'],
         ['Moments', 'Pressure moments won', '15%', 'Pressure overs won', '15%', '0.16 / 0.05'],
         ['Rise vs self', 'Pressure minus own baseline', '10%', 'Pressure minus own baseline', '10%', '0.01 / −0.05'],
         ]
S += [tbl(wrows, [22 * mm, 38 * mm, 13 * mm, 38 * mm, 13 * mm, 24 * mm]),
      P('*Correlation between odd- and even-numbered matches for each component (batting / bowling). Dots and runs repeat; rise-vs-self does not repeat at all, which is the '
        'summary finding. Moments and rise-vs-self stay in at low weight because the brief asks for match situations and comparison with usual levels.', 'cap')]

# ---------- 4. fair comparisons
S += [H1('4 · Fair comparisons'),
      B('A batter needs at least 10 pressure moments and 60 pressure balls to be rated; a bowler needs 15 pressure overs and 90 pressure balls. Everyone must have played in 2025 '
        'or 2026, because the question is who performs under pressure now. That leaves 127 batters and 120 bowlers.'),
      B('Runs against Hong Kong should not count like runs against Australia, so each ball is weighted by the opponent: 1.0 for IPL sides and full members, 0.8 for Ireland '
        'and Zimbabwe, 0.75 for A teams and 0.5 for associates. Recent cricket counts more (2026 at 1.0, then 0.9, 0.8, 0.65, and 0.55 for 2022), and knockout matches are '
        'weighted 1.25. Section 8 tests each of these choices.'),
      B('IPL and T20I balls go into one model, but each competition and season has its own scoring environment, and the dashboard shows every player\'s IPL-only pressure '
        f"numbers next to the combined ones. For players with at least 40 pressure balls in both, their pressure numbers in the IPL and in T20Is correlate at {TR['bat']['r']:.2f} "
        f"for batters ({TR['bat']['n']} players) and {TR['bowl']['r']:.2f} for bowlers ({TR['bowl']['n']}): positive, but loose. Three ranked players, Towhid Hridoy, "
        'Sufiyan Muqeem and Gudakesh Motie, have never played the IPL and are flagged.'),
      B('Batters are credited with runs off the bat and charged for their own dismissal. Bowlers answer for everything except run-outs. Extras never count against the batter. '
        'I dropped the 25 DLS-shortened games along with abandoned games and no-results, and I do not score super overs.')]
S += [H1('5 · Evidence for the top 10'),
      P('How sure am I about each rank? I resampled the matches 300 times and re-ranked everyone each time. In Figure 3 the dot is the player\'s rank and the bar covers 80% '
        'of the resamples. A short bar near the top is a player I am confident about. A long one is a player the data likes but has not seen enough of. '
        'Vaibhav Sooryavanshi is the clearest case: second on 121 pressure balls, with a range from 1 to 59.'),
      Table([[img(c4a, FW * .49), img(c4b, FW * .49)]], colWidths=[FW * .5, FW * .5]),
      P('Figure 3. Rank uncertainty for the ranked players.', 'cap')]
br = [['#', 'Batter', 'Balls', 'SR (exp)', 'Avg', 'Dot% (exp)', 'Moments won', 'P(top10)']]
for c in D['bat_top']:
    p = c['pressure']; ms = c['moment_stats']
    br.append([c['rank'], c['name'], p['balls'], f"{p['sr']:.0f} ({p['xsr']:.0f})", f"{p['avg']:.0f}", f"{p['dot']:.0f} ({p['xdot']:.0f})", f"{ms['won']}/{ms['n']} ({ms['won'] / ms['n'] * 100:.0f}%)", f"{c['p_top10']:.0f}%"])
wr = [['#', 'Bowler', 'Balls', 'Econ (exp)', 'Balls/wkt', 'Dot% (exp)', 'Overs won', 'P(top10)']]
for c in D['bowl_top']:
    p = c['pressure']; ms = c['moment_stats']
    wr.append([c['rank'], c['name'], p['balls'], f"{p['econ']:.2f} ({p['xecon']:.2f})", f"{p['bpw']:.0f}", f"{p['dot']:.0f} ({p['xdot']:.0f})", f"{ms['won']}/{ms['n']} ({ms['won'] / ms['n'] * 100:.0f}%)", f"{c['p_top10']:.0f}%"])
cw = [7 * mm, 36 * mm, 17 * mm, 23 * mm, 14 * mm, 21 * mm, 26 * mm, 16 * mm]
S += [PageBreak(), H2('Pressure-ball numbers for the ranked players'), tbl(br, cw), Spacer(1, 8), tbl(wr, cw),
      P(f"Pressure balls only. The figure in brackets is what the same situations on the same pitches normally produce. Moments won is the consistency measure; the average "
        f"is {EPB:.0f}% for batters and {EPW:.0f}% for bowlers.", 'cap'),
      PageBreak()]

# ---------- 6. instance evidence
S += [H1('6 · The moments behind the numbers'),
      P('A rating is easier to believe when you can point at the match. The figure below replays the top-ranked batter\'s best pressure innings ball by ball, and the table '
        'gives one moment for each ranked player. The dashboard goes further, with three of the best and the single worst moment for more than 60 players, each one replayable.'),
      img(c6, FW * .9),
      P(f"Figure 4. {c0['name']}, {mo['comp']}, {mo['date']}. He walked in at {mo['situation']} and made {mo['did'].split(' under')[0]}. Pink dots are the balls he faced. "
        f"{mo['result']}.", 'cap')]
mr = [[Paragraph('<b>Player</b>', ss['cellb']), Paragraph('<b>Match</b>', ss['cellb']), Paragraph('<b>Walked into</b>', ss['cellb']),
       Paragraph('<b>Did</b>', ss['cellb']), Paragraph('<b>Win %</b>', ss['cellb'])]]
for c in D['bat_top'] + D['bowl_top']:
    m = c['moments'][0]
    mr.append([Paragraph(c['name'], ss['cell']), Paragraph(f"{m['comp']}<br/>vs {m['opp']}{' (KO)' if m.get('ko') else ''}", ss['cell']),
               Paragraph(m['situation'], ss['cell']), Paragraph(m['did'].replace(' under pressure', '').replace(' — ', ', '), ss['cell']), Paragraph(m['wp'].replace(' (bowling side)', ''), ss['cell'])])
S += [tbl(mr, [27 * mm, 33 * mm, 50 * mm, 40 * mm, 22 * mm], font=7.2), Spacer(1, 10)]

# ---------- 7. auction board + RR fit
cl = RR['close']
AVL = {'available': 'In pool', 'rumoured': 'Rumoured', 'contracted': 'Under contract', 'rr': 'RR player', 'retired': 'Retired', 'ineligible': 'Not eligible'}
AC = D['avail_counts']; buy = lambda k: AC[k]['available'] + AC[k]['rumoured']
t10b = lambda k: [x for x in D['avail_top10'][k] if x['avail'] in ('available', 'rumoured')]
S += [H1('7 · From the ranking to an auction board for RR'),
      P('The ranking answers who performs best under pressure. A franchise has a second question: who can it actually buy? For the IPL 2027 mini-auction (Goa, 16 December 2026) '
        'I take out four groups before building RR\'s board: players already at RR, players retired from the IPL (Ashwin, Russell, Mohit Sharma, Vijay Shankar and Karn Sharma), '
        'players who cannot enter the auction (Pakistan nationals, and Harry Brook, who is serving a two-season IPL ban), and players in another franchise\'s 2026 squad. '
        f"That leaves {HL(buy('bat'))} of {sum(AC['bat'].values())} rated batters and {HL(buy('bowl'))} of {sum(AC['bowl'].values())} rated bowlers. "
        f"Only {len(t10b('bat'))} of the top 10 batters and {len(t10b('bowl'))} of the top 10 bowlers are among them."),
      P('Retention lists are due on 17 November 2026, so this step is provisional. Until they land, every player in another 2026 squad counts as retained, except players '
        'widely reported as likely releases; those stay on the board marked as rumoured. The rest of the board works as before: players in rating order, skipping one only when he '
        'would break a cap or leave too few places for a role the squad needs.')]
board_rows = [['#', 'Batter (model rank)', 'Role', 'Status', '#', 'Bowler (model rank)', 'Role', 'Status']]
for i in range(10):
    a, c = D['bat_board'][i], D['bowl_board'][i]
    board_rows.append([str(i + 1), f"{a['name']} ({a['raw_rank']})", a['role'], AVL[a['avail']], str(i + 1), f"{c['name']} ({c['raw_rank']})",
                       c['role'].replace('Pace · ', '').replace('Left-arm ', 'LA ').replace('New ball', 'New ball'), AVL[c['avail']]])
vr = [['', 'Batting rules', 'Bowling rules'],
      ['Caps', '≤3 openers · ≤4 IPL-untested · model rank 80 or better', '≤5 spinners · ≤4 IPL-untested · model rank 80 or better'],
      ['Minimums', '≥2 No. 3–4 · ≥3 middle order or finisher · ≥2 left-handers', '≥3 death bowlers · ≥2 new-ball · ≥2 wrist spin · ≥1 finger spin · ≥2 left-arm']]
vr = [[Paragraph(str(x), ss['cell'] if i else ss['cellb']) for x in r] for i, r in enumerate(vr)]
S += [tbl(board_rows, [5 * mm, 38 * mm, 21 * mm, 20 * mm, 5 * mm, 38 * mm, 25 * mm, 20 * mm], font=7.2), Spacer(1, 4), tbl(vr, [18 * mm, 76 * mm, 78 * mm]),
      P('Almost everyone RR can buy in this data is from overseas, because domestic Indian players mostly sit outside the T20I and IPL matches in the data pack. The overseas '
        'cap therefore belongs at the squad-building stage, not on this list. All of this is generated from one file (availability.py), so the board can be rebuilt as soon '
        'as the official lists are published.', 'cap'),
      P('Where do RR lose games under pressure? In IPL 2025–26 their batting ranked 6th of 10 on win probability gained per 100 pressure balls. The openers were better than '
        f"the league. Numbers 5 to 7 and the tail were well below it, and the death overs were the worst phase with the bat. With the ball, RR leaked at the death with pace and spin alike. "
        f"They won {cl['won']} of their {cl['n']} close games."),
      img(c5, FW * .9),
      P('Figure 5. RR minus league average, win % per 100 pressure balls. Pink is below the league. Sample sizes are printed because some are small (powerplay spin is 15 balls).', 'cap')]
fit = [['Pick', 'How he strengthens RR']]
def fit_txt(c, kind):
    s = c['splits']
    if kind == 'bat':
        t = []
        if c['role'] in ('Middle order', 'Finisher'): t.append("bats where RR leak most, at 5 to 7")
        if c['role'] == 'Top order': t.append('a No. 3 or 4 who scores above expectation under pressure')
        if c['role'] == 'Opener': t.append('an opener to pair with or cover Jaiswal and Sooryavanshi')
        if s['death'][2] >= 30 and s['death'][0] > s['death'][1]: t.append(f"strikes at {s['death'][0]:.0f} in death-overs pressure (expected {s['death'][1]:.0f})")
        if s['vs_spin'][2] >= 30 and s['vs_spin'][0] > s['vs_spin'][1]: t.append(f"{s['vs_spin'][0]:.0f} against spin (expected {s['vs_spin'][1]:.0f})")
        if c['in_rr']: t.append('already at RR, so the case is to build around him')
        if not c['ipl_seasons']: t.append('has never played the IPL, so the price should allow for that')
    else:
        t = []
        if s['death'][2] >= 18 and s['death'][0] < s['death'][1]: t.append(f"goes at {s['death'][0]:.2f} in death-overs pressure (expected {s['death'][1]:.2f}), which is where RR leak")
        if c.get('kind') != 'Pace': t.append("adds to a middle-overs spin attack that is already RR's strength")
        if 'New ball' in str(c.get('phase_role')): t.append('can take the new ball as well')
        if s['middle'][2] >= 30 and s['middle'][0] < s['middle'][1] and c.get('kind') == 'Pace': t.append(f"a pace option through the middle ({s['middle'][0]:.2f} against {s['middle'][1]:.2f})")
    t = '; '.join(t)
    return t[:1].upper() + t[1:]
for c in D['bat_board']: fit.append([Paragraph(f"<b>{c['name']}</b> ({c['role']})", ss['cell']), Paragraph(fit_txt(c, 'bat'), ss['cell'])])
for c in D['bowl_board']: fit.append([Paragraph(f"<b>{c['name']}</b> ({c['role'].replace('Pace · ', 'Pace, ')})", ss['cell']), Paragraph(fit_txt(c, 'bowl'), ss['cell'])])
fit[0] = [Paragraph('<b>Board pick</b>', ss['cellb']), Paragraph('<b>How he strengthens RR</b>', ss['cellb'])]
S += [PageBreak(), H2('How each board pick strengthens RR'), tbl(fit, [55 * mm, 117 * mm]), PageBreak()]

# ---------- 7b. match simulator
SX = json.load(open(f'{OUT}/sim_examples.json')); SV = json.load(open(f'{OUT}/sim_validation.json'))
mm_ = SX['moment_match']
S += [H2('What if: replaying RR\'s 2025–26 games'),
      P('The dashboard has a match simulator for testing a pick in a real game. You choose one of RR\'s 29 IPL 2025–26 matches, stop it at any ball, and swap one RR batter or '
        'bowler for someone else. The rest of the match is then replayed 2,000 times, ball by ball. On every ball the chance of a dot, 1, 2, 3, 4, 6 or a wicket starts '
        'from the IPL 2025–26 average for that phase and type of bowling. It is then adjusted by the batter\'s record and the bowler\'s record in that phase against that '
        'type, both shrunk hard towards average when the sample is small, and by how each of them changes on pressure balls. A small model (AUC 0.86) estimates how likely '
        'each simulated ball is to be a pressure ball. The batting order and the over-by-over bowling plan stay as they were, and the old and new teams use the same random '
        'numbers, so any gap comes from the players and not from luck.'),
      P(f"Checked against reality on {SV['all']['sim'][0]} game states (five points in every IPL 2025–26 match), the simulator's win chances score a Brier of "
        f"{HL(format(SV['all']['sim'][1], '.3f'))}, against {SV['all']['engine'][1]:.3f} for the win-probability model in section 2 and 0.250 for a coin toss. Simulated first-innings "
        f"totals average {SV['first_inn_mean_sim']} against {SV['first_inn_mean_actual']} in the real games.")]
mr_ = [['RR v ' + mm_['opp'].split()[0] + ' ' + mm_['date'][:4] + ': moment', 'Striker taken out', 'RR win chance (real side)'] + [x[0] for x in SX['moment'][0]['swaps']]]
for r in SX['moment']:
    mr_.append([f"after {r['ov']} ov: {r['score']}/{r['wk']}, need {r['need']} off {r['balls']}", r['striker'], f"{r['base']:.0f}%"] + [f"{x[1]:.0f}%" for x in r['swaps']])
mr_ = [[Paragraph(str(x), ss['cellb'] if i == 0 else ss['cell']) for x in r] for i, r in enumerate(mr_)]
sr_ = [['Board pick', 'Replaces in every game', 'Games', 'Extra wins expected', 'Real defeats that flip']]
for r in SX['season']:
    sr_.append([r['name'], ('RR\'s ' + r['rule']) if r['kind'] == 'bat' else 'RR\'s ' + r['rule'], str(r['n']), f"{r['gain']:+.2f}", str(len(r['flips']))])
S += [Spacer(1, 4), tbl(mr_, [34 * mm, 22 * mm, 22 * mm, 23 * mm, 23 * mm, 23 * mm, 23 * mm], font=7.2),
      P(f"{mm_['result']}. The table restarts that chase at two moments and puts four of the board's batters on strike in place of the man who was there.", 'cap'),
      Spacer(1, 6), tbl(sr_, [38 * mm, 44 * mm, 16 * mm, 34 * mm, 40 * mm], font=7.6),
      P('Season replay: each pick plays every RR game from the first ball (games he played in are skipped). "Extra wins" adds up the change in RR\'s win chance across the '
        'games; a defeat "flips" when the real side loses it in most replays and the new one wins it in most. One player rarely moves a whole game by more than a few points '
        'from ball one, so differences under about half a win are within the noise.', 'cap'),
      PageBreak()]

# ---------- 7c. scouting, backups, retain/release
SCT = json.load(open(f'{OUT}/scout.json'))
buyg = lambda k: [g for g in SCT['gems'][k] if g['avail'] in ('available', 'rumoured')][:5]
S += [H2('Scouting beyond the scorecard'),
      P('Strike rate and economy weigh every ball the same, but a game can turn on one boundary or one dot ball. To find players the ranking might underrate, I '
        'compare two percentiles for every rated player. One is his ordinary scorecard (strike rate and average, or economy and balls per wicket). The other is his pressure '
        'impact: 60% the win probability he adds per pressure ball, 40% how often a single ball of his moves the game by five points or more, both shrunk towards zero for '
        'small samples. A "hidden gem" sits in the top 30% for pressure impact and at least 15 points higher on impact than on the scorecard.')]
gr = [['', 'Player', 'Nation', 'Rank', 'Scorecard pct', 'Pressure impact pct', 'Game-turning balls']]
for k, lab_ in (('bat', 'Bat'), ('bowl', 'Bowl')):
    for g in buyg(k): gr.append([lab_, g['name'], g['nat'], str(g['rank']), str(g['conv_p']), str(g['imp_p']), f"{g['big']} in {g['pb']}"])
S += [tbl(gr, [12 * mm, 40 * mm, 26 * mm, 14 * mm, 24 * mm, 30 * mm, 30 * mm], font=7.4),
      P('Hidden gems RR can buy, by gem score. Game-turning balls: pressure balls that each moved the win chance by 5+ points.', 'cap'),
      P('A second list widens the net to nations outside the usual IPL pipeline (Zimbabwe, Ireland, Bangladesh, the UAE, Scotland and others), using every player with 40 '
        'or more pressure balls even if he misses the rating\'s evidence threshold. Much of their cricket is against weaker sides, so the dashboard shows the share of each '
        'player\'s pressure balls against Full-member or IPL opposition and whether his impact held up there. Sikandar Raza, Mohammad Saif Hassan, Towhid Hridoy, George Dockrell, '
        'Mark Adair and Craig Young lead it. These are end-of-auction punts, not core signings.'),
      P('Auctions are unpredictable, so every target on the board has three fallbacks from the same role: a cheap-value option (best rated with low or medium expected demand), '
        'a bidding-war option (the alternative other teams will want most) and an under-the-radar option (the best gem score). The data has no prices, so demand is estimated '
        'from scorecard numbers, IPL experience and recent volume. The full plan is in the dashboard.')]
rt = [r for r in SCT['retain'] if (r['salary'] or 0) > 1]
small_ = [r for r in SCT['retain'] if r['salary'] and r['salary'] <= 1]
rr_ = [['Player', 'Salary (cr)', 'Best rank', 'Wins added for RR*', 'Model call']]
for r in rt:
    br = min([x for x in [r['bat_rank'], r['bowl_rank']] if x] or [None]) if (r['bat_rank'] or r['bowl_rank']) else None
    rr_.append([r['name'], f"{r['salary']}", str(br) if br else '–', f"{r['rr_wpa'] / 100:+.2f}" if r['rr_pb'] >= 20 else '–', r['rec']])
S += [H2('Retain and release: the same lens on RR\'s squad'),
      P('Applied to RR\'s own 2026 squad and salaries, the model keeps the players who rate well under pressure and questions the expensive ones who do not. "Release and buy '
        'back" marks a useful player on a premium salary whom other teams are unlikely to chase hard. These are model calls only: captaincy, wicketkeeping, fitness, age and the '
        'Indian-player quota are not in the data and would change some of them.'),
      tbl(rr_, [44 * mm, 22 * mm, 20 * mm, 32 * mm, 52 * mm], font=7.2),
      P('*Win probability added for RR on pressure balls in IPL 2025–26, bat and ball combined; +1.00 is one extra win. Salaries from public IPL 2026 squad lists. '
        f"The {len(small_)} players on 1 crore or less are mostly kept as cheap depth; the model would release " + ', '.join(r['name'] for r in small_ if r['rec'] == 'Release') + '.', 'cap'),
      PageBreak()]

# ---------- 8. reliability, robustness and limitations
sen_rows = [['Change to the method', 'Batting top 10 kept', 'Bowling top 10 kept']]
for k in SEN['bat']:
    sen_rows.append([k, f"{SEN['bat'][k]['overlap']}/10 (ρ {SEN['bat'][k]['spearman']:.2f})", f"{SEN['bowl'][k]['overlap']}/10 (ρ {SEN['bowl'][k]['spearman']:.2f})"])
S += [H1('8 · Reliability, robustness and limitations'),
      P('If a score does not repeat, it is measuring luck. I tested mine two ways. First I rated every player separately on his odd-numbered and even-numbered matches and '
        'correlated the two. Then I rated on 2022–24 alone and on 2025–26 alone.'),
      img(c3, FW * .86),
      P(f"Figure 6. Across eras the rating holds and the raw clutch score does not. Within the same seasons the edge is smaller: "
        f"{V['bat']['split_half_prr']:.2f} against {V['bat']['split_half_naive']:.2f} for batters and {V['bowl']['split_half_prr']:.2f} against {V['bowl']['split_half_naive']:.2f} for bowlers. "
        f"Each of those is a half-sample correlation; on the full sample (Spearman-Brown) it corresponds to a reliability of about {SB['bat']:.2f} and {SB['bowl']:.2f}.", 'cap'),
      P('An earlier version of this analysis reported odd-even figures of 0.35 and 0.26. Those were inflated by a bug: the match split was computed separately for balls and for '
        'pressure moments, so the two halves overlapped. The figures above use one split for everything. The rankings were not affected, only the validation.'),
      P('How much do my own choices drive the ranking? I changed each hand-set choice in turn and re-ranked everyone.'),
      tbl(sen_rows, [92 * mm, 40 * mm, 40 * mm]),
      P('ρ is the rank correlation with the submitted rating across all eligible players. The last row is the important benchmark: rating players on their all-ball skill '
        'alone, with no pressure information, keeps only half of each top 10. The pressure measurement changes who is on the list.', 'cap'),
      H2('Where I am less sure'),
      B('Pressure performance is noisy, and no model will change that. Ranks 5 to 10 are a tier rather than exact places, and the bars in Figure 3 are the honest picture. '
        f"On a strict prediction test, rating players on half their matches and predicting their pressure-ball performance in the other half, the rating scores "
        f"{RB['predictive']['bat']['PRR']:.2f} for batters and {RB['predictive']['bowl']['PRR']:.2f} for bowlers, and the all-ball baseline does slightly better "
        f"({RB['predictive']['bat']['Baseline only']:.2f} and {RB['predictive']['bowl']['Baseline only']:.2f}). I kept the rating because the brief asks how players perform under "
        "pressure compared with their usual level, which a baseline-only score cannot answer; the cost is a little predictive power."),
      B('Win probability in the first innings is the weaker half of the model (AUC 0.70), so pressure is identified less sharply for sides batting first. Captains also give '
        'the high-pressure overs to their best bowlers and choose matchups, so pressure balls are not a random sample; the opponent weighting only partly corrects for that.'),
      B('The data records the stroke and the type of delivery but not line, length, shot direction, edges or the field. The shot and delivery mixes and the decision versus '
        'execution split in the dashboard are descriptive only, and none of them feeds the rating. Roles are inferred from where a player has batted or bowled across the whole '
        'period, so someone who changed role recently may carry the old label.'),
      B('Availability is provisional until the retention lists of 17 November 2026. Release rumours come from press reports, not official lists, and are marked as such.'),
      B('The match simulator uses player records that include the same RR games it replays, and it does not model the toss, dew, injuries or captaincy. It is a way to '
        'compare two players in the same situation, not a forecast of what would have happened.')]
S += [H1('9 · Reproducibility'),
      P('The pipeline is a set of Python scripts run in order on the supplied files, and every number in this report and the dashboard comes out of them. The random seeds are '
        'fixed, so running the scripts again gives the same numbers. It takes a few minutes on a laptop.'),
      P('Model choice: with 5-fold cross-validation grouped by match, scikit-learn gradient boosting, LightGBM and CatBoost finished within 0.4% of each other on every task '
        'and all beat a linear model. CatBoost was a hair more accurate but no more repeatable, so I kept scikit-learn with fixed seeds.'),
      tbl([['Step', 'Script', 'What it does'],
           ['1', 'engine.py', 'Scoring environment, win-probability models, leverage, pressure balls, per-ball win probability added'],
           ['2', 'reliab2.py', 'Expected runs / dismissal / dot / wicket per ball'],
           ['3', 'moments.py', 'Pressure moments, roles, nationality, shot and delivery DNA, squeeze and bounce-back'],
           ['4', 'ratings2.py', 'PRR components, weighting, bootstrap rank bands, split-half and era validation'],
           ['5', 'rr_gaps.py / availability.py / select.py', 'RR gap analysis, auction availability, ranking, auction board, dashboard data'],
           ['6', 'robust.py / model_cmp.py', 'Sensitivity, baseline benchmark, IPL vs T20I transfer, model comparison'],
           ['7', 'sim_export.py / sim.js', 'Player outcome profiles, RR match data, simulator and its validation']],
          [12 * mm, 40 * mm, 120 * mm]),
      Spacer(1, 10)]

# ---------- appendix
S += [PageBreak(), H1('Appendix · Top 15 by PRR')]
for key, kind in [('bat_table', 'Batters'), ('bowl_table', 'Bowlers')]:
    rows = [['Rank', 'Player', 'Role', 'Nation', 'PRR', '80% band', 'P(top10)', 'Ranked', 'Board']]
    for r in D[key][:15]:
        rows.append([r['rank'], r['name'], r['role'].replace('Pace · ', 'Pace, '), r['nat'], f"{r['prr']:.1f}", f"{r['lo']}–{r['hi']}", f"{r['p10']:.0f}%", '●' if r['selected'] else '', '●' if r.get('board') else ''])
    S += [H2(kind), tbl(rows, [10 * mm, 34 * mm, 42 * mm, 22 * mm, 11 * mm, 16 * mm, 14 * mm, 12 * mm, 12 * mm], font=7)]
doc.build(S)
print('built', PDF)

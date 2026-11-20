"""Shared SMAT helpers: name linking to the data pack, IPL 2027 status, exclusions, veterans, bowling style.
Editable inputs live in datasets/: ipl2027_retention.csv, exclusions.csv, birth_years.csv, bowling_styles.csv."""
import os, re, sys, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from ipl2027_lists import RET, REL
D = os.path.join(HERE, 'datasets')
EXC = pd.read_csv(os.path.join(D, 'exclusions.csv'))
EXCL_FULL = {r.name: r.reason for r in EXC.itertuples() if r.match_on == 'full'}
EXCL_CS = {r.name: r.reason for r in EXC.itertuples() if r.match_on == 'cricsheet'}
BORN = dict(pd.read_csv(os.path.join(D, 'birth_years.csv'))[['name', 'born']].values)
STY = {r.name: (r.style, r.arm) for r in pd.read_csv(os.path.join(D, 'bowling_styles.csv')).itertuples()}
POOL = ('uncapped', 'ipl_unsigned', 'ipl_released')

def toks(n): return re.sub(r'[^A-Za-z ]', ' ', n).split()
def is_init(t): return t.isupper() and len(t) <= 3
OVERRIDE = {'SA Yadav': 'Suryakumar Yadav', 'RK Singh': 'Rinku Singh', 'Atharva Taide': 'Atharwa Taide', 'KV Sharma': 'Karn Sharma', 'DS Kulkarni': 'Dhawal Kulkarni',
            'Abdul Samad': 'Abdul Samad'}
RET_TOK = [(n, t, toks(n)) for n, t in RET.items()]

class Linker:
    def __init__(self, DATA):
        mp = pd.read_csv(f'{DATA}/competition_team_player_mapping.csv')
        ipl = mp[mp.comp_name.str.startswith('IPL')]
        self.team26 = ipl[ipl.comp_name == 'IPL 2026'].drop_duplicates('player_id').set_index('player_id').team_name
        self.ipl_seasons = ipl.groupby('player_id').comp_name.nunique()
        names = mp.drop_duplicates('player_id')[['player_id', 'player_name']]
        self.idx, self.by_name = {}, {}
        for pid, nm in names.values:
            t = toks(nm)
            if t: self.idx.setdefault(t[-1].lower(), []).append((pid, nm, t))
            self.by_name.setdefault(nm, []).append(pid)
        bb = pd.read_csv(f'{DATA}/ball_by_ball.csv', usecols=['bowler_id', 'bowling_type'])
        self.btype = bb.dropna().groupby('bowler_id').bowling_type.agg(lambda s: s.mode().iat[0])

    def link(self, cs):
        ips = self.ipl_seasons
        if cs in OVERRIDE:
            nm = OVERRIDE[cs]; ids = sorted(self.by_name.get(nm, []), key=lambda p: -ips.get(p, 0))
            return (ids[0], nm, toks(nm)) if ids else (None, nm, toks(nm))
        t = toks(cs)
        if not t: return None
        cand = self.idx.get(t[-1].lower(), [])
        full = [c for c in cand if ' '.join(c[2]).lower() == ' '.join(t).lower()]
        if full: return sorted(full, key=lambda c: -ips.get(c[0], 0))[0]
        words = [w.lower() for w in t if not is_init(w)]
        sub = [c for c in cand if words and all(w in [x.lower() for x in c[2]] for w in words) and len(words) >= 2]
        if len(sub) == 1: return sub[0]
        inits = ''.join(w for w in t if is_init(w))
        if inits:
            ini = [c for c in cand if c[2][0][0].upper() == inits[0] and not is_init(c[2][0])]
            if len(ini) > 1: ini = [c for c in ini if c[0] in ips.index] or ini
            if len(ini) == 1: return ini[0]
        return None

    @staticmethod
    def ret_team(cs, full):
        if full and full in RET: return RET[full]
        t = toks(cs or '')
        if not t: return None
        if ' '.join(t) in RET: return RET[' '.join(t)]
        sur, first = t[-1].lower(), t[0]
        c = {tm for n, tm, tt in RET_TOK if tt[-1].lower() == sur and (tt[0].lower() == first.lower() or (is_init(first) and tt[0][0].upper() == first[0]))}
        return c.pop() if len(c) == 1 else None

    def status(self, cs, last='2024/25', first='2024/25', in_form=False):
        """-> dict(full, pid, status, ipl_team, excluded_reason, veteran, ipl_seasons, bowling_type)"""
        m = self.link(cs) if cs else None
        pid, full = (m[0], m[1]) if m else (None, None)
        t26 = self.team26.get(pid) if pid else None
        ns = int(self.ipl_seasons.get(pid, 0)) if pid else 0
        t27 = self.ret_team(cs, full)
        exc = EXCL_FULL.get(full) or EXCL_CS.get(cs)
        if exc: st = 'retired'
        elif t27 == 'Rajasthan Royals': st = 'rr'
        elif t27: st = 'contracted'
        elif (full in REL) or t26: st = 'ipl_released'
        elif ns: st = 'ipl_unsigned'
        else: st = 'uncapped'
        if st in ('uncapped', 'ipl_unsigned') and last < '2022/23' and ns == 0 and not in_form: st = 'inactive'
        born = min(BORN.get(cs, 2100), BORN.get(full or '', 2100))
        vet = bool(first <= '2015/16' or born <= 1993)
        bt = self.btype.get(pid) if pid else None
        return {'full': full, 'pid': pid, 'status': st, 'ipl_team': t27 or t26, 'excluded': exc, 'veteran': vet, 'ipl_seasons': ns, 'bowling_type': bt}

def style_of(cs, full, bowling_type):
    """(style, arm, source) from manual CSV, then data-pack bowling type."""
    for n in (cs, full):
        if n and n in STY: return STY[n][0], STY[n][1], 'manual'
    if isinstance(bowling_type, str):
        spin = any(k in bowling_type for k in ('Break', 'break', 'orthodox', 'Chinaman'))
        return ('spin' if spin else 'pace'), ('left' if bowling_type.startswith('Left') else 'right'), 'data pack'
    return None, None, None

"""Habillage musical des podcasts MACROARSENAL (10/11/2026). Kévin : « habillage musique différent de la radio pour les
podcasts », « un truc en vogue qui irait bien avec les podcasts ».

Direction : lo-fi chill-hop teinté de future garage, celle des podcasts business et tech actuels. Tempo 90 (la zone où
une voix parlée ne « court » pas après la musique), batterie feutrée avec un léger swing (grosse caisse ronde, caisse
claire douce posée un peu en arrière, charleston et vrai shaker en doubles croches swinguées), accords de Rhodes en
septièmes et neuvièmes, basse sub chaude, piano droit, texture de vinyle discrète et pleurage de bande.

La signature : un motif court, « Mi-La », la quarte qui monte. M et A, les initiales de MACROARSENAL, lues en solfège
(Mi, La). Le motif ouvre le générique (Mi-La, Sol-Mi), revient dans chaque transition, et le générique de fin le
referme sur le La. Rien du télégraphe de la radio : ni morse, ni bip.

Harmonie (la mineur) : Fa maj9 → Mi7sus4 / Mi7 → Ré m9 → Mi7sus4 → La (quinte et neuvième, sans tierce : un accord
ouvert qui ne gêne pas la voix qui entre dessus).

Tout est composé ici : synthèse numpy (Rhodes en modulation de fréquence, basse, grosse caisse, charleston, souffle de
vinyle) et vrais instruments enregistrés du domaine public (VSCO 2 Community Edition, CC0 : piano droit, caisse claire,
shaker, glockenspiel). Aucun échantillon sous licence, aucune musique téléchargée.

Usage : VSCO=~/vsco python podcast/habillage.py <sortie>
Sorties : generique, transition-a, transition-b, transition-c, fond, fond-doux, fin (.flac 48 kHz stéréo ; .mp3 d'écoute
avec --mp3) et reperes.json (instants où la voix entre, tempo : lus par podcast/mixage.py).
"""
import functools, glob, json, os, re, subprocess, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'son'))
from lib import SR, compress, db, eq, fade, impulse, limiter, loudness, pad_to, pan, pitch, place, reverb, save, stereo  # noqa: E402

V = os.environ.get('VSCO', os.path.expanduser('~/vsco'))
OUT = sys.argv[1] if len(sys.argv) > 1 else 'podcast/habillage'
MP3 = '--mp3' in sys.argv
os.makedirs(OUT, exist_ok=True)

BPM = 90
BEAT = 60 / BPM
S16 = BEAT / 4
BAR = 4 * BEAT
SWING = 0.18 * S16          # les doubles croches « faibles » arrivent un peu en retard : le balancement du hip-hop
LAYBACK = 0.012             # la caisse claire posée juste derrière le temps


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tl(d):
    return np.arange(int(round(d * SR))) / SR


def bus(d):
    return np.zeros((int(round(d * SR)), 2), np.float32)


def put(b, x, t, gain=1.0, p=None):
    place(b, pan(x, p) if p is not None else x, t, gain)


def at(bar, beat=0.0):
    """Instant (s) d'un temps : mesure (0 = première) et temps dans la mesure (0 à 4)."""
    return bar * BAR + beat * BEAT


def swing(t16):
    """Instant d'une double croche (0 à 15 dans la mesure), avec le swing sur les doubles croches impaires."""
    return t16 * S16 + (SWING if t16 % 2 else 0.0)


# --- Harmonie -----------------------------------------------------------------------------------------------------------
# Accords : basse (MIDI) et voicing du Rhodes (main droite), en la mineur.
CH = {
    'Fmaj9': (41, [57, 60, 64, 67]),        # Fa : la do mi sol (Fa maj9 sans fondamentale à la main droite)
    'E7sus': (40, [57, 62, 64, 71]),        # Mi : la ré mi si
    'E7': (40, [56, 62, 64, 71]),           # Mi : sol# ré mi si
    'Dm9': (38, [53, 57, 60, 64]),          # Ré : fa la do mi
    'Em7': (40, [55, 59, 62, 64]),          # Mi : sol si ré mi
    'Am9': (45, [60, 64, 67, 71]),          # La : do mi sol si
    'A5add9': (33, [52, 57, 59, 64, 69]),   # La ouvert (quinte, neuvième, sans tierce) : l'accord d'arrivée
}
# Le motif « Mi-La » : (temps dans la mesure, durée en temps, note MIDI)
MOTIF = [(0.0, 0.5, 76), (0.5, 1.5, 81), (2.0, 0.5, 79), (2.5, 1.5, 76)]                 # Mi La Sol Mi
REPONSE = [(0.0, 0.5, 74), (0.5, 0.5, 72), (1.0, 1.5, 71), (2.5, 1.5, 68)]               # Ré Do Si Sol#
MONTEE = [(0.0, 0.5, 76), (0.5, 1.0, 81), (1.5, 0.5, 83), (2.0, 1.0, 84), (3.0, 1.0, 83)]  # Mi La Si Do Si
CADENCE = [(0.0, 1.0, 81), (1.0, 1.0, 80), (2.0, 2.0, 76)]                                 # La Sol# Mi
MOTIF_COURT = [(0.0, 0.5, 76), (0.5, 1.0, 81), (1.5, 0.5, 79), (2.0, 2.0, 76)]            # transitions : Mi La Sol Mi


# --- Instruments de synthèse ----------------------------------------------------------------------------------------------
def rhodes(midi, dur, vel=0.6, rel=0.35, seed=0):
    """Piano électrique en modulation de fréquence (rapport 1:1 pour la lame, 14:1 pour le « tintement » d'attaque) :
    plus on frappe fort, plus le son est brillant ; les notes graves tiennent plus longtemps."""
    f = hz(midi)
    t = tl(dur + rel)
    idx = (0.7 + 1.9 * vel) * (0.3 + 0.7 * np.exp(-t / 0.28))
    ph = np.random.default_rng(seed + midi).uniform(0, 6.28)
    tine = np.sin(2 * np.pi * f * t + ph + idx * np.sin(2 * np.pi * f * t))
    bark = np.sin(2 * np.pi * f * t + 1.4 * np.exp(-t / 0.010) * np.sin(2 * np.pi * 14 * f * t)) * np.exp(-t / 0.045)
    body = np.sin(2 * np.pi * f * t + ph)
    T = float(np.clip(1.7 * (440 / f) ** 0.4, 0.8, 3.2))
    env = np.minimum(1, t / 0.0025) * (0.25 + 0.75 * np.exp(-t / T)) * np.exp(-t / (T * 3))
    nr = int(rel * SR)
    env[len(t) - nr:] *= np.cos(np.linspace(0, np.pi / 2, nr)) ** 2
    x = (0.62 * tine + 0.10 * vel * bark + 0.35 * body) * env * vel
    x = np.tanh(1.4 * x) / np.tanh(1.4)
    return eq(x.astype(np.float32), ('hp', 70), ('lp', 5200))


def tremolo(x, rate=4.0, depth=0.16, t0=0.0):
    """Le vibrato stéréo d'un vrai Rhodes : le son va et vient doucement entre gauche et droite."""
    x = stereo(x)
    t = t0 + np.arange(len(x)) / SR
    m = depth * np.sin(2 * np.pi * rate * t)
    return np.stack([x[:, 0] * (1 + m), x[:, 1] * (1 - m)], 1).astype(np.float32)


def chord_rhodes(name, dur, vel=0.5, strum=0.012, seed=0, top=None):
    _, notes = CH[name]
    notes = notes if top is None else [n for n in notes if n <= top]
    n = int((dur + 0.6) * SR)
    out = np.zeros((n, 2), np.float32)
    for i, m in enumerate(notes):
        x = rhodes(m, dur, vel * (0.85 + 0.15 * (i == len(notes) - 1)), seed=seed + i)
        place(out, pan(stereo(x), -0.25 + 0.5 * i / max(1, len(notes) - 1)), i * strum)
    return out


def sub(midi, dur, vel=0.7, rel=0.08):
    """Basse sub chaude : sinus et un peu d'harmonique 2 (audible sur un petit haut-parleur), légère saturation."""
    f = hz(midi)
    t = tl(dur + rel)
    x = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(4 * np.pi * f * t + 0.6)
    env = np.minimum(1, t / 0.012)
    nr = int(rel * SR)
    env[len(t) - nr:] *= np.cos(np.linspace(0, np.pi / 2, nr)) ** 2
    x = np.tanh(1.6 * x * env) / np.tanh(1.6) * vel
    return stereo(eq(x.astype(np.float32), ('lp', 420), ('hp', 28)))


def kick(vel=0.9, seed=0):
    """Grosse caisse ronde et feutrée : sinus qui tombe de 118 à 49 Hz, presque pas de clic."""
    t = tl(0.5)
    f = 49 + (118 - 49) * np.exp(-t / 0.028)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.2)
    x = np.tanh(1.25 * x) / np.tanh(1.25)
    nc = int(0.006 * SR)
    c = np.random.default_rng(seed).standard_normal(nc) * np.exp(-np.arange(nc) / (0.0012 * SR))
    x[:nc] += 0.05 * c / (np.abs(c).max() + 1e-9)
    return stereo(fade(eq(x.astype(np.float32), ('lp', 2400)) * vel, 0.0005, 0.06))


def _noise(n, seed, corr=0.6):
    r = np.random.default_rng(seed)
    a, b = r.standard_normal(n), r.standard_normal(n)
    return np.stack([a, corr * a + (1 - corr) * b], 1)


def hat(vel=0.25, decay=0.022, seed=0):
    """Charleston fermé doux : du souffle filtré haut, très court (pas de métal agressif)."""
    t = tl(0.12)
    x = _noise(len(t), seed, 0.5) * np.exp(-t / decay)[:, None]
    x = eq(x.astype(np.float32), ('hp', 7000), ('peak', 9500, 2.0, 1.0), ('lp', 13000))
    return (x / (np.abs(x).max() + 1e-9) * vel).astype(np.float32)


@functools.lru_cache(None)
def vsco(rel):
    from lib import load
    x = load(os.path.join(V, rel))
    m = np.abs(x).max(1)
    i = int(np.argmax(m > m.max() * 0.02))
    x = x[max(0, i - int(0.001 * SR)):]
    return x * (db(-6) / max(1e-6, np.abs(x).max()))


@functools.lru_cache(None)
def piano_bank(dyn):
    out = {}
    for p in sorted(glob.glob(os.path.join(V, f'Keys/Upright Piano/Player_dyn{dyn}_rr1_*.wav'))):
        k = int(re.search(r'_(\d{3})\.wav$', p).group(1))
        out[21 + 2 * k] = os.path.relpath(p, V)
    assert out, 'piano VSCO introuvable (VSCO=…)'
    return out


def piano(midi, dur, vel=0.5, rel=0.5):
    """Vrai piano droit (VSCO 2 CE), la note la plus proche transposée, étouffée à la fin de sa durée."""
    b = piano_bank(1 if vel < 0.55 else 2)
    src = min(b, key=lambda k: abs(k - midi))
    x = pitch(vsco(b[src]), midi - src) * (0.35 + 0.65 * vel)
    n = int((dur + rel) * SR)
    return fade(pad_to(x, n)[:n].copy(), 0.002, rel)


SNARE = 'Percussion/Snare2-HitSN_v3_rr1_Sum.wav'
SNARE2 = 'Percussion/Snare2-HitSN_v3_rr2_Sum.wav'
SHAKERS = sorted(glob.glob(os.path.join(V, "VSCO 1 Percussion/varWood/Camo's Shaker/shake*.wav")))
GLOCK = 'Percussion/Glock/glock_medium_C6.wav'      # sonne une octave au-dessus de son nom (mesuré dans son/sfx.py)


def snare(vel=0.5, rr=0):
    """Caisse claire douce : vraie caisse claire (VSCO) adoucie, et un souffle court qui lui donne du corps."""
    x = vsco(SNARE if rr % 2 == 0 else SNARE2)[: int(0.5 * SR)]
    x = eq(x, ('hp', 160), ('peak', 220, 2.0, 1.2), ('lp', 6500))
    t = tl(0.25)
    nz = _noise(len(t), 77 + rr, 0.7) * np.exp(-t / 0.07)[:, None]
    nz = eq(nz.astype(np.float32), ('hp', 1400), ('lp', 6000))
    y = pad_to(stereo(x), len(t)) * 1.0 + nz / (np.abs(nz).max() + 1e-9) * 0.25
    return fade((y / (np.abs(y).max() + 1e-9) * vel).astype(np.float32), 0.0005, 0.08)


def shaker(vel=0.2, k=0):
    x = vsco(os.path.relpath(SHAKERS[k % len(SHAKERS)], V))[: int(0.25 * SR)]
    return fade(eq(x, ('hp', 2500), ('lp', 11000)) * vel, 0.0, 0.05)


def glock(midi, vel=0.25):
    return pitch(vsco(GLOCK), midi - 96) * vel


def vinyl(d, vel=1.0, seed=0):
    """Texture de vinyle : souffle doux, craquements rares (sans « pop » agressif)."""
    n = int(d * SR)
    r = np.random.default_rng(seed)
    hiss = eq((r.standard_normal((n, 2)) * 0.012).astype(np.float32), ('hp', 3000), ('lp', 9000))
    x = np.zeros(n, np.float32)
    for i in r.integers(0, max(1, n - 96), r.poisson(7 * d)):
        x[i:i + 64] += r.uniform(-1, 1) * 0.5 * np.exp(-np.arange(64) / 6.0)
    pops = eq(x, ('hp', 900), ('lp', 7000))
    return ((hiss + stereo(pops) * 0.6) * vel).astype(np.float32)


def wow(x, depth_ms=1.2, rate=0.45, seed=0):
    """Pleurage de bande : la hauteur ondule à peine (la patine « lo-fi »)."""
    x = stereo(x); n = len(x); i = np.arange(n, dtype=np.float64)
    ph = np.random.default_rng(seed).uniform(0, 6.28)
    d = depth_ms / 1000 * SR * (0.5 + 0.5 * np.sin(2 * np.pi * rate * i / SR + ph))
    src = np.clip(i - d, 0, n - 1)
    return np.stack([np.interp(src, i, x[:, c]) for c in range(2)], 1).astype(np.float32)


ROOM = impulse(rt60=1.1, pre=0.012, bright=5500, damp=2400, width=1.0, seed=41)
PLATE = impulse(rt60=0.7, pre=0.004, bright=8000, damp=4200, width=1.0, seed=42)


def duck_by(x, kicks, depth_db=-3.0, rel=0.16):
    """Pompe douce : les claviers s'effacent un instant à chaque grosse caisse (le son « moderne » du lo-fi)."""
    g = np.ones(len(x), np.float32)
    for t in kicks:
        i = int(t * SR)
        n = min(len(x) - i, int(0.45 * SR))
        if n <= 0:
            continue
        tt = np.arange(n) / SR
        g[i:i + n] = np.minimum(g[i:i + n], 1 - (1 - db(depth_db)) * np.exp(-tt / rel))
    return (x * g[:, None]).astype(np.float32)


# --- Une partition, des pistes -------------------------------------------------------------------------------------------
class Piste:
    """Pistes séparées (claviers, basse, batterie, ambiance), mixées à la fin avec leurs traitements."""

    def __init__(self, d):
        self.keys, self.lead, self.bass, self.drums, self.amb = (bus(d) for _ in range(5))
        self.kicks = []

    def accord(self, name, t, dur, vel=0.5, seed=0, basse=True, bvel=0.55, top=None):
        put(self.keys, tremolo(chord_rhodes(name, dur, vel, seed=seed, top=top), t0=t), t)
        if basse:
            put(self.bass, sub(CH[name][0], dur, bvel), t)

    def motif(self, notes, bar0, t0, vel=0.55, octave_rhodes=True, glock_first=False):
        for b, d, m in notes:
            t = t0 + at(bar0, b)
            put(self.lead, piano(m, d * BEAT, vel), t, p=0.12)
            if octave_rhodes:
                put(self.lead, tremolo(rhodes(m - 12, d * BEAT, vel * 0.55, seed=m)), t, 0.6, p=-0.1)
        if glock_first:
            put(self.lead, glock(notes[0][2] + 12, 0.18), t0 + at(bar0, notes[0][0]), p=0.3)

    def groove(self, t0, bars, vel=1.0, snare_on=True, hats=True, fill=False, kick_pattern=None):
        """Mesures de batterie : grosse caisse sur 1, le « et » de 2 (fantôme) et 3 et quart ; caisse claire sur 2 et 4."""
        kp = kick_pattern or [(0, 1.0), (7, 0.45), (10, 0.85)]
        for k in range(bars):
            tb = t0 + k * BAR
            for s, v in kp:
                put(self.drums, kick(0.9 * v * vel, seed=k * 16 + s), tb + swing(s))
                self.kicks.append(tb + swing(s))
            if snare_on:
                for s in (4, 12):
                    put(self.drums, snare(0.42 * vel, rr=k * 2 + s), tb + swing(s) + LAYBACK, p=0.04)
            if hats:
                for s in range(16):
                    if s % 2 == 0 or s in (3, 11, 15):
                        put(self.drums, hat(0.13 * vel * (1.0 if s % 4 == 0 else 0.72), seed=k * 16 + s), tb + swing(s), p=0.22)
                    if s % 2 == 1:
                        put(self.drums, shaker(0.10 * vel, k * 16 + s), tb + swing(s), p=-0.3)
            if fill and k == bars - 1:
                for s, v in ((13, 0.22), (14, 0.28), (15, 0.34)):
                    put(self.drums, snare(v * vel, rr=s), tb + swing(s) + LAYBACK, p=0.04)

    def mix(self, d, keys_db=-5.0, lead_db=2.0, bass_db=-4.0, drums_db=-3.0, vinyl_db=-30.0, seed=0, lp=None, duck=True):
        keys = reverb(wow(self.keys, seed=seed), ROOM, wet_db=-13)[: len(self.keys)]
        if duck and self.kicks:
            keys = duck_by(keys, self.kicks, -3.0)
        lead = reverb(wow(self.lead, depth_ms=0.9, seed=seed + 1), ROOM, wet_db=-11)[: len(self.lead)]
        drums = reverb(self.drums, PLATE, wet_db=-19)[: len(self.drums)]
        drums = eq(drums, ('lp', 9000), ('lowshelf', 120, 1.5))
        bass = self.bass
        if duck and self.kicks:
            bass = duck_by(bass, self.kicks, -4.0, rel=0.12)
        x = keys * db(keys_db) + lead * db(lead_db) + bass * db(bass_db) + drums * db(drums_db)
        x = x + pad_to(vinyl(len(x) / SR + 0.01, seed=seed), len(x)) * db(vinyl_db + 30)
        x = x + self.amb
        if lp:
            x = eq(x, ('lp', lp))
        return x


def master(x, name, lufs=-16.0, fin=0.0, fout=0.3, loop=False, mids=0.0):
    """Égalisation (bas coupé, aigus adoucis : la patine), compression de « colle », volume, limiteur, écriture."""
    x = eq(x, ('hp', 30), ('peak', 320, -1.5, 0.9), ('highshelf', 10000, -2.0))
    if mids:   # fonds : on creuse la zone de la voix
        x = eq(x, ('peak', 1600, mids, 0.6), ('peak', 600, mids / 2, 0.9))
    x, _ = compress(x, threshold_db=-20, ratio=2.2, attack=0.015, release=0.16, knee_db=8)
    if not loop:
        x = fade(x, fin, fout)
    x = limiter(x * db(lufs - loudness(x)[0]), ceiling_db=-1.0)
    path = os.path.join(OUT, name + '.flac')
    tmp = os.path.join(OUT, name + '.wav')
    save(tmp, x)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', tmp, '-c:a', 'flac', '-compression_level', '8', path], check=True)
    if MP3:
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', tmp, '-b:a', '192k', os.path.join(OUT, name + '.mp3')], check=True)
    os.remove(tmp)
    i, tp, _ = loudness(x)
    print(f'{name} : {len(x) / SR:.2f} s, {i:.1f} LUFS, crête {tp:.1f} dBTP', flush=True)
    return x


def reverse_swell(name, d=0.9, vel=0.5):
    """Accord inversé : la réverbération d'un accord jouée à l'envers, qui aspire vers le temps fort (transition)."""
    c = chord_rhodes(name, 1.2, vel)
    w = reverb(c, impulse(rt60=2.2, pre=0.01, bright=6000, damp=2500, seed=7), wet_db=0, dry=0.0)
    w = w[: int(2.2 * SR)][::-1]
    w = w[-int(d * SR):]
    return fade(w, d * 0.6, 0.02) * 0.9


# --- Les pièces ------------------------------------------------------------------------------------------------------------
REP = {'bpm': BPM, 'mesure': BAR, 'style': 'lofi-chillhop', 'motif': 'Mi-La (M et A en solfège)'}


def generique():
    """Générique d'ouverture (≈ 14 s) : le groove et le motif dès la première mesure, quatre mesures, puis l'accord ouvert
    sur lequel la voix entre (la fin de l'accord tient sous les premiers mots)."""
    t0 = 0.3
    d = t0 + 4 * BAR + 3.6
    P = Piste(d)
    prog = [('Fmaj9', 4), ('E7sus', 2), ('E7', 2), ('Dm9', 4), ('E7sus', 2), ('E7', 2)]
    t = t0
    for k, (c, beats) in enumerate(prog):
        P.accord(c, t, beats * BEAT - 0.03, vel=0.5, seed=k)
        t += beats * BEAT
    P.groove(t0, 4, vel=1.0, fill=True)
    P.motif(MOTIF, 0, t0, vel=0.6, glock_first=True)
    P.motif(REPONSE, 1, t0, vel=0.52)
    P.motif(MONTEE, 2, t0, vel=0.58)
    P.motif(CADENCE, 3, t0, vel=0.55)
    tf = t0 + 4 * BAR
    P.accord('A5add9', tf, 3.2, vel=0.5, seed=9, bvel=0.6)
    put(P.drums, kick(0.95), tf); P.kicks.append(tf)
    put(P.lead, piano(69, 2.5, 0.5), tf, p=0.1)
    put(P.lead, glock(93, 0.16), tf, p=0.3)
    x = P.mix(d, seed=1)
    # ouverture : le filtre s'ouvre sur la première mesure (de 900 Hz au son plein)
    lpv = eq(x, ('lp', 900), ('lp', 900))
    n1 = int((t0 + BAR) * SR)
    w = np.clip(np.arange(len(x)) / n1, 0, 1)[:, None] ** 1.5
    x = lpv * (1 - w) + x * w
    REP['generique_voix'] = round(tf + 0.35, 3)
    REP['generique_duree'] = round(d, 3)
    return master(x, 'generique', lufs=-15.0, fin=0.15, fout=1.6)


def transition(name, chord, seed):
    """Transition entre deux chapitres (≈ 3,8 s) : un accord inversé aspire vers le temps fort, le motif court sur une
    mesure de groove, puis l'accord tient pendant que la voix revient."""
    pre = 0.85
    d = pre + BAR + 1.6
    P = Piste(d)
    put(P.amb, reverse_swell(chord), 0.0)
    P.accord(chord, pre, BAR + 0.6, vel=0.48, seed=seed)
    P.groove(pre, 1, vel=0.85, kick_pattern=[(0, 1.0), (10, 0.7)])
    P.motif(MOTIF_COURT, 0, pre, vel=0.55, glock_first=(seed == 0))
    x = P.mix(d, seed=seed + 3, drums_db=-4.0)
    REP[f'{name}_voix'] = round(pre + BAR * 0.8, 3)
    REP[f'{name}_duree'] = round(d, 3)
    return master(x, name, lufs=-17.0, fin=0.02, fout=1.2)


def fond(name, doux=False):
    """Fond sous la voix (8 mesures, en boucle) : accords et basse ; avec un groove très léger (fond) ou sans (fond-doux).
    Jamais le motif (il resterait accroché à l'oreille), et la zone de la voix creusée."""
    bars = 8
    d = bars * BAR
    P = Piste(d + 3.0)
    prog = (['Fmaj9', 'Em7', 'Dm9', 'Am9', 'Fmaj9', 'Em7', 'Dm9', 'E7sus'] if not doux else
            ['Fmaj9', 'Fmaj9', 'Dm9', 'Dm9', 'Am9', 'Am9', 'E7sus', 'E7sus'])
    for k, c in enumerate(prog):
        if doux and k % 2:
            continue
        P.accord(c, k * BAR, (2 if doux else 1) * BAR - 0.05, vel=0.36 if doux else 0.42, seed=k,
                 bvel=0.42 if doux else 0.5)
    if not doux:
        P.groove(0.0, bars, vel=0.55, snare_on=False, kick_pattern=[(0, 1.0), (10, 0.6)])
    x = P.mix(d, seed=11 if doux else 12, drums_db=-8.0, lp=3800 if doux else 6000, duck=not doux)
    n = int(d * SR)                       # boucle : la queue revient au début
    x[: len(x) - n] += x[n:]
    x = x[:n]
    return master(x, name, lufs=-24.0 if doux else -22.0, loop=True, mids=-4.0)


def fin():
    """Générique de fin (≈ 20 s) : deux mesures douces sous les derniers mots, puis le groove entre (« drop ») avec le
    motif, sa réponse, la montée, la cadence, et l'arrivée sur La : le motif est refermé."""
    soft = 2
    d = (soft + 4) * BAR + 4.5
    P = Piste(d)
    for k, c in enumerate(['Fmaj9', 'E7sus']):
        P.accord(c, k * BAR, BAR - 0.03, vel=0.4, seed=k, bvel=0.45)
    prog = [('Fmaj9', 4), ('E7sus', 2), ('E7', 2), ('Dm9', 4), ('E7sus', 2), ('E7', 2)]
    t = soft * BAR
    for k, (c, beats) in enumerate(prog):
        P.accord(c, t, beats * BEAT - 0.03, vel=0.52, seed=10 + k)
        t += beats * BEAT
    P.groove(soft * BAR, 4, vel=1.0, fill=True)
    P.motif(MOTIF, soft, 0.0, vel=0.6, glock_first=True)
    P.motif(REPONSE, soft + 1, 0.0, vel=0.52)
    P.motif(MONTEE, soft + 2, 0.0, vel=0.58)
    P.motif(CADENCE, soft + 3, 0.0, vel=0.55)
    tf = (soft + 4) * BAR
    P.accord('A5add9', tf, 4.0, vel=0.5, seed=19, bvel=0.6)
    put(P.drums, kick(0.95), tf); P.kicks.append(tf)
    put(P.lead, piano(69, 3.2, 0.5), tf, p=0.1)
    put(P.lead, piano(76, 3.0, 0.42), tf + BEAT * 0.5, p=0.1)     # Mi… La : la signature, une dernière fois
    put(P.lead, piano(81, 3.0, 0.45), tf + BEAT * 1.0, p=0.1)
    put(P.lead, glock(93, 0.16), tf + BEAT, p=0.3)
    x = P.mix(d, seed=21)
    REP['fin_drop'] = round(soft * BAR, 3)
    REP['fin_duree'] = round(d, 3)
    return master(x, 'fin', lufs=-15.0, fin=0.3, fout=2.5)


# --- Variante B : future garage / électro douce (même harmonie, même motif) ------------------------------------------------
def tempo(bpm, swing_ratio):
    """Change le tempo de toute la partition (les fonctions lisent ces valeurs au moment de jouer)."""
    global BPM, BEAT, S16, BAR, SWING
    BPM = bpm; BEAT = 60 / bpm; S16 = BEAT / 4; BAR = 4 * BEAT; SWING = swing_ratio * S16


def pad(name, dur, vel=0.3, seed=0):
    """Nappe chaude : dents de scie légèrement désaccordées, filtrées bas, attaque lente (l'air du future garage)."""
    _, notes = CH[name]
    t = tl(dur + 0.8)
    out = np.zeros((len(t), 2))
    r = np.random.default_rng(seed)
    for i, m in enumerate(notes):
        for v, c in enumerate((-9.0, 0.0, 9.0)):
            f = hz(m) * 2 ** (c / 1200)
            ph = r.uniform(0, 6.28)
            s = sum(np.sin(k * (2 * np.pi * f * t + ph)) / k for k in range(1, 9))
            a = (v / 2) * np.pi / 2
            out[:, 0] += s * np.cos(a); out[:, 1] += s * np.sin(a)
    env = np.minimum(1, t / 0.6) * np.minimum(1, np.maximum(0, (dur + 0.8 - t) / 0.8))
    x = (out * env[:, None] * vel / (3 * len(notes))).astype(np.float32)
    return eq(x, ('lp', 1400), ('lp', 2200), ('hp', 180))


def pluck(midi, vel=0.5, seed=0):
    """Pluck de synthèse : une note brève et ronde dont le filtre se referme vite (le motif en version électro)."""
    f = hz(midi)
    t = tl(0.9)
    ph = np.random.default_rng(seed + midi).uniform(0, 6.28)
    s = sum(np.exp(-t * 9.0 * (k - 1)) * np.sin(k * (2 * np.pi * f * t + ph)) / k for k in range(1, 12))
    env = np.minimum(1, t / 0.002) * np.exp(-t / 0.32)
    return stereo(eq((s * env * vel).astype(np.float32), ('lp', 6500), ('hp', 200)))


def echo(x, d, fb=0.35, n=4, lp=3500):
    """Écho ping-pong (gauche, droite) qui s'assombrit à chaque répétition."""
    x = stereo(x)
    out = pad_to(x.copy(), len(x) + int(d * SR * (n + 1)))
    y = x
    for k in range(1, n + 1):
        y = eq(y, ('lp', lp), ('hp', 300)) * fb
        place(out, y[:, ::-1] if k % 2 else y, k * d)
    return out


def generique_b():
    """Variante B du générique (≈ 13 s) : 2-step future garage à 130, en demi-temps sous le motif. Nappe, basse sub qui
    roule, claquement et caisse claire sur 2 et 4, charleston très balancé, le motif Mi-La au pluck avec un écho."""
    tempo(130, 0.30)
    t0 = 0.25
    bars = 6
    d = t0 + bars * BAR + 3.4
    P = Piste(d)
    prog = [('Fmaj9', 2.0), ('E7sus', 1.0), ('E7', 1.0), ('Dm9', 1.0), ('E7sus', 0.5), ('E7', 0.5)]   # en mesures à 130
    t = t0
    for k, (c, nb) in enumerate(prog):
        dur = nb * BAR
        put(P.keys, pad(c, dur, 0.55, seed=k), t)
        put(P.keys, tremolo(chord_rhodes(c, min(dur, BAR) * 0.9, 0.32, seed=k), t0=t), t, 0.8)
        put(P.bass, sub(CH[c][0], dur - 0.05, 0.55), t)
        t += dur
    for k in range(bars):
        tb = t0 + k * BAR
        for s, v in ((0, 1.0), (7, 0.55), (10, 0.85)):            # 2-step : la grosse caisse saute le troisième temps
            put(P.drums, kick(0.9 * v), tb + swing(s)); P.kicks.append(tb + swing(s))
        for s in (4, 12):
            put(P.drums, snare(0.40, rr=k * 2 + s), tb + swing(s) + 0.006, p=0.04)
            put(P.drums, hat(0.08, decay=0.06, seed=k + s), tb + swing(s) + 0.012, p=-0.1)
        for s in range(16):
            if s % 2 == 1 or s in (2, 14):
                put(P.drums, hat(0.12 * (1.0 if s in (2, 6, 10, 14) else 0.6), seed=k * 16 + s), tb + swing(s), p=0.25)
        if k == 0:
            for s in (2, 6, 10, 14):
                put(P.drums, shaker(0.10, k * 16 + s), tb + swing(s), p=-0.3)
    # le motif au pluck, en demi-temps (une note du motif = deux fois plus longue), avec son écho
    lead = bus(d)
    for bar0, notes in ((0, MOTIF), (2, REPONSE), (4, CADENCE)):
        for b, du, m in notes:
            tt = t0 + bar0 * BAR + b * 2 * BEAT        # demi-temps : un temps du motif = deux temps à 130
            place(lead, pan(pluck(m, 0.55, seed=bar0), 0.08), tt)
            place(lead, pan(stereo(piano(m, du * 2 * BEAT, 0.42)), -0.08), tt, 0.5)
    P.lead += pad_to(echo(lead, 3 * S16), len(P.lead))[: len(P.lead)] * 0.9
    tf = t0 + bars * BAR
    P.accord('A5add9', tf, 3.0, vel=0.45, seed=9, bvel=0.6)
    put(P.keys, pad('A5add9', 3.0, 0.5, seed=9), tf)
    put(P.drums, kick(0.95), tf); P.kicks.append(tf)
    put(P.lead, piano(69, 2.5, 0.5), tf, p=0.1)
    put(P.lead, glock(93, 0.15), tf, p=0.3)
    x = P.mix(d, seed=5, vinyl_db=-36.0)
    lpv = eq(x, ('lp', 700), ('lp', 700))
    n1 = int((t0 + BAR) * SR)
    w = np.clip(np.arange(len(x)) / n1, 0, 1)[:, None] ** 1.5
    x = lpv * (1 - w) + x * w
    REP['generique-b_voix'] = round(tf + 0.35, 3)
    REP['generique-b_duree'] = round(d, 3)
    out = master(x, 'generique-b', lufs=-15.0, fin=0.15, fout=1.6)
    tempo(90, 0.18)
    return out


if __name__ == '__main__':
    if '--variante-b' in sys.argv:
        generique_b()
        sys.exit(0)
    generique()
    for k, (n, c) in enumerate((('transition-a', 'Fmaj9'), ('transition-b', 'Dm9'), ('transition-c', 'Am9'))):
        transition(n, c, k)
    fond('fond')
    fond('fond-doux', doux=True)
    fin()
    REP['fichiers'] = ['generique', 'transition-a', 'transition-b', 'transition-c', 'fond', 'fond-doux', 'fin']
    json.dump(REP, open(os.path.join(OUT, 'reperes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(REP, ensure_ascii=False))

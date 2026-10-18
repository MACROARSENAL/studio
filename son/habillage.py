"""Identité sonore n° 2 de MACROARSENAL Radio (18/10/2026). Kévin voulait « un truc plus percutant, atypique, vraiment à nous ».

La signature : « MA » en morse (— — · —). Le morse est le langage du télégraphe, l'ancêtre des téléscripteurs de la Bourse.
Posé sur une mesure de seize doubles croches, le code tombe pile : longue sur le 1, longue sur le 2, brève sur le « et » du 3,
longue sur le 4 (« DOUM, DOUM, ta-DOUM »). Toute l'identité en découle :
  - l'indicatif : les bips du télégraphe (direction « télégraphe »), puis toute la batterie frappe le même code ;
  - le carillon des nouvelles : la lettre A (· —) ;
  - la virgule entre deux rubriques : le code en accéléré ;
  - le souvenir de salle : le code au loin, sur une vieille radio ;
  - l'indicatif de fin ;
  - les fonds, dont la pulsation reprend le code à chaque mesure.
L'enclume frappe toujours la brève : c'est la forge de l'arsenal, où l'on prépare ses outils (son plan, son stop).

Harmonie : ré « ouvert » (quinte et neuvième, ni majeur ni mineur), préparé par do (le septième degré, couleur mixolydienne) ;
si bémol en chemin dans les fonds. Tempo 120 : une mesure = 2 secondes.

Deux directions, même partition :
  telegraphe : électro et percussions hybrides (sub, claps, charleston de téléscripteur, nappes et accords de synthé),
               avec une vraie grosse caisse géante et une vraie enclume pour le poids ;
  forge      : cinéma (grosse caisse géante, timbales, toms, enclume, gong, cuivres graves, cordes en spiccato).
Tout est composé ici : synthèse numpy (additive, sans repliement) et vrais instruments enregistrés (VSCO 2 Community
Edition, domaine public CC0). Rien n'est imité : composition originale.

Usage : VSCO=~/vsco python son/habillage.py <telegraphe|forge> <sortie>
Sorties : intro, carillon, virgule, souvenir, fin, fond, fond-ecrans, fond-souvenir (.wav 48 kHz stéréo + .mp3)
          et reperes.json (instants où la voix entre, tempo : lus par radio/mixage.py).
"""
import functools, glob, json, os, re, subprocess, sys

import numpy as np
from scipy import signal

from lib import SR, compress, db, eq, fade, impulse, limiter, loudness, pad_to, pan, pitch, place, reverb, save, stereo
from sfx import V, midi_of, sample

STYLE = sys.argv[1] if len(sys.argv) > 1 else 'telegraphe'
OUT = sys.argv[2] if len(sys.argv) > 2 else f'habillage-{STYLE}'
assert STYLE in ('telegraphe', 'forge'), STYLE
TEL = STYLE == 'telegraphe'
os.makedirs(OUT, exist_ok=True)

BPM = 120
BEAT = 60 / BPM
S16 = BEAT / 4
BAR = 16 * S16
CODE = ((0, 3, 'M'), (4, 3, 'M'), (10, 1, 'dit'), (12, 3, 'A'))   # « MA » : (début, longueur) en doubles croches
MORSE = {'M': '--', 'A': '.-'}
# Accords « ouverts » : fondamentale, quinte, neuvième, quinte, octave (MIDI)
CH = {'D': [38, 45, 52, 57, 62], 'C': [36, 43, 50, 55, 60], 'Bb': [34, 41, 48, 53, 58]}
PROG = ['D', 'D', 'C', 'C', 'Bb', 'Bb', 'C', 'C']                    # les 8 mesures du fond


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tl(dur):
    return np.arange(int(round(dur * SR))) / SR


def bus_of(dur):
    return np.zeros((int(round(dur * SR)), 2), np.float32)


def put(bus, x, t, gain=1.0, p=None):
    place(bus, pan(x, p) if p is not None else x, t, gain)


# --- Vrais instruments (VSCO 2 CE) ------------------------------------------------------------------------------------
BANKS = {
    'cello': 'Strings/Cello Section/susvib/*.wav', 'viola': 'Strings/Viola Section/susvib/*.wav',
    'violin': 'Strings/Violin Section/susVib/*.wav', 'cello-spic': 'Strings/Cello Section/spic/*.wav',
    'cb-spic': 'Strings/Solo Contrabass/Spic/*.wav', 'violin-spic': 'Strings/Violin Section/Spic/*.wav',
    'cello-trem': 'Strings/Cello Section/trem/*.wav',
    'horn': 'Brass/F Horn/sus/*.wav', 'horn-stac': 'Brass/F Horn/stac/*.wav', 'tbn-stac': 'Brass/Tenor Trombone/stac/*.wav',
    'tuba-stac': 'Brass/Tuba/stac/*.wav', 'harp': 'Strings/Harp/KSHarp_*_mf.wav', 'glock': 'Percussion/Glock/glock_medium_*.wav',
    'marimba': 'Percussion/Marimba/Marimba_hit_Outrigger_*_loud_01.wav',
}


@functools.lru_cache(None)
def bank(kind, vel=2):
    """{note MIDI : fichier} ; pour chaque note, la couche de vélocité la plus proche de vel, première alternance."""
    if kind == 'piano':
        out = {}
        for p in sorted(glob.glob(os.path.join(V, 'Keys/Upright Piano/Player_dyn2_rr1_*.wav'))):
            k = int(re.search(r'_(\d{3})\.wav$', p).group(1))
            out[21 + 2 * k] = os.path.relpath(p, V)
        return out
    shift = 0 if kind == 'harp' else 12   # mesuré : ces échantillons sonnent une octave au-dessus de leur nom (sauf la harpe)
    best = {}
    for p in sorted(glob.glob(os.path.join(V, BANKS[kind]))):
        b = os.path.basename(p)
        try:
            m = midi_of(b) + shift
        except AttributeError:
            continue
        v = re.search(r'_v(\d)', b)
        rr = 0 if re.search(r'(rr|RR)1|_1\.wav$', b) else 1
        key = (abs((int(v.group(1)) if v else vel) - vel), rr, b)
        if m not in best or key < best[m][0]:
            best[m] = (key, os.path.relpath(p, V))
    assert best, kind
    return {m: f for m, (_, f) in best.items()}


LAYER = {'tbn-stac': 3, 'horn-stac': 3, 'cello': 3, 'tuba-stac': 2}


def note(kind, midi, vel=0.8, dur=None, rel=0.25, layer=None):
    b = bank(kind, layer or LAYER.get(kind, 2))
    src = min(b, key=lambda k: abs(k - midi))
    x = pitch(sample(b[src]), midi - src) * (0.25 + 0.75 * vel)
    if vel < 0.95:
        x = eq(x, ('lp', 2200 + 10000 * vel))
    if dur is not None:
        n = int((dur + rel) * SR)
        x = fade(pad_to(x, n)[:n].copy(), 0.0, rel)
    return x


def perc(rel, vel=1.0, semis=0.0):
    x = sample(rel)
    return (pitch(x, semis) if semis else x) * vel


ANVIL = 'Percussion/Anvil_Hit1_v2_Sum.wav'          # ≈ 2 030 Hz : accordée sur la (quinte de ré) avec −2,5 demi-tons
GIANT = 'VSCO 1 Percussion/drums/other/ethnic/giant/mallet/EthnicLargeMallet_hit_ff_1.wav'
GIANT_SOFT = 'VSCO 1 Percussion/drums/other/ethnic/giant/hand/EthnicLargeHand_hit_mp_1.wav'
BDRUM = 'Percussion/BDrumNewhit_v7_rr1_Sum.wav'
TIMP = 'Percussion/Timpani/Timpani3_Hit_v3_rr1_Sum.wav'   # ≈ 71 Hz : +0,6 demi-ton = ré grave
TIMP_ROLL = 'Percussion/Timpani/Rolls/Timpani3_Roll_v5_rr1_Sum.wav'
TENOR = 'VSCO 1 Percussion/drums/tenor/tenor_lower/tenor_fff_1.wav'
CRASH = 'Percussion/cymbal-crash1_mf_rr1.wav'
SWELL = 'Percussion/susCymb1-cresc-Short_v1.wav'
GONG = 'Percussion/gongHit_f.wav'


def anvil(vel=0.8):
    return perc(ANVIL, vel, -2.5)


def timp(midi=38, vel=0.7):
    return perc(TIMP, vel, midi - 37.4)


# --- Synthèse ----------------------------------------------------------------------------------------------------------
def saw(midi, dur, vel=0.8, rel=0.2, voices=3, detune=10.0, kmax=40, dk=0.0, decay=None, attack=0.003, width=0.6, seed=0):
    """Dent de scie additive, sans repliement. dk : les harmoniques aiguës s'éteignent plus vite (un filtre qui se referme).
    decay : décroissance du volume (s). voices : voix légèrement désaccordées (largeur stéréo)."""
    n = int(round((dur + rel) * SR)); t = np.arange(n) / SR
    f0 = hz(midi); r = np.random.default_rng(seed * 131 + int(midi * 7))
    out = np.zeros((n, 2))
    for v in range(voices):
        c = 0.0 if voices == 1 else (v / (voices - 1) - 0.5) * 2 * detune
        f = f0 * 2 ** (c / 1200)
        K = max(1, int(min(kmax, 0.45 * SR / f)))
        w = 2 * np.pi * f * t + r.uniform(0, 2 * np.pi)
        s = np.zeros(n)
        for k in range(1, K + 1):
            s += (np.exp(-t * dk * (k - 1)) if dk else 1.0) / k * np.sin(k * w)
        a = ((0.0 if voices == 1 else (v / (voices - 1) - 0.5) * 2 * width) + 1) * np.pi / 4
        out[:, 0] += s * np.cos(a); out[:, 1] += s * np.sin(a)
    env = np.ones(n)
    na = max(1, int(attack * SR)); env[:na] = np.linspace(0, 1, na) ** 1.5
    if decay:
        env *= np.exp(-t / decay)
    nr = int(rel * SR)
    if nr:
        env[n - nr:] *= np.cos(np.linspace(0, np.pi / 2, nr)) ** 2
    return (out * env[:, None] * (vel / voices)).astype(np.float32)


def stab(chord, dur, vel=0.6, dk=1.4, decay=0.6, rel=0.25, voices=3, detune=12, kmax=36, seed=0):
    x = None
    for i, m in enumerate(chord):
        y = saw(m, dur, vel * (1.0 if i else 1.15), rel, voices, detune, kmax, dk, decay, seed=seed + i)
        x = y if x is None else pad_to(x, max(len(x), len(y))) + pad_to(y, max(len(x), len(y)))
    return x


def sine(midi, dur, vel=0.8, rel=0.15, attack=0.004, decay=None):
    t = tl(dur + rel); x = np.sin(2 * np.pi * hz(midi) * t)
    env = np.minimum(1, t / attack)
    if decay:
        env = env * np.exp(-t / decay)
    nr = int(rel * SR)
    env[len(t) - nr:] *= np.cos(np.linspace(0, np.pi / 2, nr)) ** 2
    return stereo((x * env * vel).astype(np.float32))


def kick(vel=1.0, f_hi=150.0, f_lo=45.0, tau=0.035, decay=0.32, dur=0.7, click=0.3, drive=1.8, seed=0):
    """Grosse caisse de synthèse : sinus dont la hauteur tombe vite (l'impact), un clic court, une saturation douce."""
    t = tl(dur)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / tau)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    x = np.tanh(drive * x) / np.tanh(drive)
    nc = int(0.008 * SR)
    c = np.random.default_rng(seed).standard_normal(nc) * np.exp(-np.arange(nc) / (0.0015 * SR))
    c = eq(c.astype(np.float32), ('hp', 1200), ('lp', 9000))
    x[:nc] += click * c / (np.abs(c).max() + 1e-9)
    return stereo(fade(x.astype(np.float32) * vel, 0.0005, 0.08))


def boom(vel=1.0, f_hi=72.0, f_lo=31.0, tau=0.4, decay=1.0, dur=2.8):
    """Le grondement des bandes-annonces : une onde très grave qui descend et s'éteint lentement."""
    t = tl(dur)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / tau)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    x = np.tanh(1.3 * x) / np.tanh(1.3)
    return stereo(fade(eq(x.astype(np.float32), ('lp', 180)) * vel, 0.002, 0.6))


def _noise(n, seed, corr=0.7):
    r = np.random.default_rng(seed)
    a, b = r.standard_normal(n), r.standard_normal(n)
    return np.stack([a, corr * a + (1 - corr) * b], 1)


def clap(vel=0.8, seed=0, tail=0.14):
    n = int(0.4 * SR); x = np.zeros((n, 2))
    nz = _noise(n, seed, 0.6)
    for k, d in enumerate((0.0, 0.010, 0.021, 0.033)):
        i = int(d * SR); m = n - i
        x[i:] += nz[:m] * np.exp(-np.arange(m) / ((0.0035 if k < 3 else tail) * SR))[:, None] * (0.75 if k < 3 else 1.0)
    x = eq(x.astype(np.float32), ('hp', 650), ('peak', 1350, 6, 0.9), ('peak', 4200, 2, 1.0), ('lp', 8500))
    return (x / np.abs(x).max() * vel).astype(np.float32)


HAT_F = (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)


def hat(vel=0.4, decay=0.028, dur=0.14, seed=0, bright=1.0):
    """Charleston métallique : six ondes carrées inharmoniques et un peu de souffle, filtrés très haut."""
    t = tl(dur); r = np.random.default_rng(seed)
    x = sum(signal.square(2 * np.pi * f * 1.62 * t + r.uniform(0, 6.28)) for f in HAT_F) / 6
    x = np.stack([x, x], 1) * 0.7 + _noise(len(t), seed, 0.5) * 0.35
    x = eq(x.astype(np.float32), ('hp', 6800), ('hp', 6800), ('peak', 10500, 3 * bright, 1.2), ('lp', 15500))
    x = x * np.exp(-t / decay)[:, None]
    return (x / (np.abs(x).max() + 1e-9) * vel).astype(np.float32)


def ticker(vel=0.3, seed=0):
    """Le cliquetis d'un téléscripteur : un déclic sec et boisé, très court."""
    n = int(0.03 * SR)
    x = _noise(n, seed, 0.8) * np.exp(-np.arange(n) / (0.0018 * SR))[:, None]
    x = eq(x.astype(np.float32), ('hp', 1800), ('peak', 3600, 7, 2.5), ('lp', 7000))
    return (x / (np.abs(x).max() + 1e-9) * vel).astype(np.float32)


def beep(dur, f=880.0, vel=0.5, edge=0.005):
    """Un bip de télégraphe (onde entretenue), bords adoucis pour ne pas claquer."""
    t = tl(dur)
    x = np.sin(2 * np.pi * f * t) + 0.05 * np.sin(4 * np.pi * f * t) + 0.02 * np.sin(6 * np.pi * f * t)
    e = np.ones(len(t)); a = int(edge * SR)
    e[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2; e[-a:] = e[:a][::-1]
    return stereo((x * e * vel).astype(np.float32))


def morse(word, unit=0.06, f=880.0, vel=0.5):
    """Bips du mot en morse ; renvoie le son et les éléments (début, durée, point ou trait)."""
    seq, t = [], 0.0
    for letter in word:
        for s in MORSE[letter]:
            d = unit * (3 if s == '-' else 1)
            seq.append((t, d, s)); t += d + unit
        t += 2 * unit
    b = bus_of(seq[-1][0] + seq[-1][1] + 0.05)
    for a, d, _ in seq:
        place(b, beep(d, f, vel), a)
    return b, seq


def bell(f=1760.0, dur=1.0, vel=0.5, ratio=3.5, index=2.2, decay=0.35):
    """Cloche FM (fréquence porteuse modulée) : un « ting » clair et métallique."""
    t = tl(dur)
    mod = index * np.exp(-t / (decay * 0.4)) * np.sin(2 * np.pi * f * ratio * t)
    x = np.sin(2 * np.pi * f * t + mod) * np.exp(-t / decay) * np.minimum(1, t / 0.001)
    return stereo((x * vel).astype(np.float32))


def riser(dur, f0=250.0, f1=8000.0, bw=0.5, vel=0.4, seed=0, curve=2.2):
    """Montée de souffle : bande de bruit qui monte (filtrage dans le domaine fréquentiel), en crescendo."""
    n = int(dur * SR); out = np.zeros((n, 2))
    w = _noise(n, seed, 0.3)
    for c in range(2):
        f, tt, Z = signal.stft(w[:, c], SR, nperseg=2048, noverlap=1536)
        fc = f0 * (f1 / f0) ** (np.clip(tt / dur, 0, 1) ** 1.3)
        mask = np.exp(-0.5 * ((np.log2(f[:, None] + 1.0) - np.log2(fc[None, :])) / bw) ** 2)
        _, y = signal.istft(Z * mask, SR, nperseg=2048, noverlap=1536)
        out[:, c] = pad_to(y, n)[:n]
    out *= (np.linspace(0, 1, n) ** curve)[:, None]
    return (out / (np.abs(out).max() + 1e-9) * vel).astype(np.float32)


def echo(x, d, fb=0.4, n=5, lp=3200, pingpong=True, dry=1.0):
    x = stereo(x)
    out = pad_to(x * dry, len(x) + int(d * SR * (n + 1)))
    y = x
    for k in range(1, n + 1):
        y = eq(y, ('lp', lp), ('hp', 250)) * fb
        place(out, y[:, ::-1] if (pingpong and k % 2) else y, k * d)
    return out


def wow(x, depth_ms=3.0, rate=0.55, seed=0):
    """Pleurage de bande magnétique : la hauteur ondule à peine, comme un vieux magnétophone."""
    x = stereo(x); n = len(x); i = np.arange(n, dtype=np.float64)
    ph = np.random.default_rng(seed).uniform(0, 6.28)
    d = depth_ms / 1000 * SR * (0.5 + 0.5 * np.sin(2 * np.pi * rate * i / SR + ph))
    src = np.clip(i - d, 0, n - 1)
    return np.stack([np.interp(src, i, x[:, c]) for c in range(2)], 1).astype(np.float32)


def vieille_radio(x, drive=1.7):
    y = eq(stereo(x), ('hp', 380), ('hp', 380), ('lp', 3300), ('lp', 3300), ('peak', 1600, 5, 1.0))
    return (np.tanh(y * drive) / np.tanh(drive)).astype(np.float32)


def crackle(dur, density=16, vel=0.05, seed=0):
    n = int(dur * SR); r = np.random.default_rng(seed)
    x = eq((r.standard_normal(n) * 0.03).astype(np.float32), ('hp', 2500), ('lp', 9000))
    for i in r.integers(0, n - 64, r.poisson(density * dur)):
        x[i:i + 48] += r.uniform(-1, 1) * np.exp(-np.arange(48) / 5.0)
    return stereo(eq(x, ('hp', 700)) * vel)


# --- Espace et finition -----------------------------------------------------------------------------------------------
HALL = impulse(rt60=1.9 if not TEL else 1.4, pre=0.02, bright=7000, damp=3000, width=1.0, seed=31)
PLATE = impulse(rt60=0.9, pre=0.006, bright=9000, damp=5000, width=1.0, seed=32)


def finish(bus, name, lufs=-16.0, wet=-14.0, fout=0.6, loop=None, glue=True, mids=0.0):
    """Réverbération, égalisation, compression de « colle » (attaque lente : les impacts passent), volume, limiteur."""
    x = reverb(bus, PLATE if TEL else HALL, wet_db=wet)
    if TEL:  # plaque courte pour l'impact, un peu de grande salle derrière pour la profondeur
        h = reverb(bus, HALL, wet_db=wet - 6, dry=0.0)
        n = max(len(x), len(h)); x = pad_to(x, n) + pad_to(h, n)
    if loop:
        n = int(loop * SR)
        x[: len(x) - n] += x[n:]
        x = x[:n]
    x = eq(x, ('hp', 28), ('peak', 300, -1.5, 0.9), ('highshelf', 9500, 1.0))
    if mids:  # fonds : on creuse la zone de la voix pour qu'elle reste parfaitement intelligible
        x = eq(x, ('peak', 1500, mids, 0.6), ('peak', 550, mids / 2, 0.9))
    if glue:
        x, _ = compress(x, threshold_db=-18, ratio=2.5, attack=0.012, release=0.14, makeup_db=0)
    x = fade(x, 0.0, fout) if not loop else x
    x = limiter(x * db(lufs - loudness(x)[0]), ceiling_db=-1.0)
    if not loop:
        m = np.abs(x).max(1)
        last = np.nonzero(m > db(-60))[0]
        x = fade(x[: (last[-1] if len(last) else len(x)) + int(0.05 * SR)], 0.0, 0.2)
        x = limiter(x * db(lufs - loudness(x)[0]), ceiling_db=-1.0)   # la queue coupée change le volume mesuré : on recale
    path = os.path.join(OUT, name + '.wav')
    save(path, x)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', path, '-b:a', '192k', os.path.join(OUT, name + '.mp3')], check=True)
    i, tp, _ = loudness(x)
    print(f'{STYLE} {name} : {len(x) / SR:.2f} s, {i:.1f} LUFS, crête {tp:.1f} dBTP', flush=True)
    return x


# --- Les frappes du code ---------------------------------------------------------------------------------------------
def frappe(b, t, kind, chord, vel=1.0, top=None, final_len=2.6, big=True):
    """Une frappe du code. kind : 'M' (longue), 'dit' (brève, l'enclume), 'A' (la longue finale, qui tient).
    big : grondement, cymbale et gong sur la finale (indicatifs) ; pas dans la virgule."""
    root = chord[0]
    if top in chord:
        top = None
    if TEL:
        if kind == 'dit':
            put(b, anvil(0.75 * vel), t, p=0.15)
            put(b, stab([chord[0] + 12, chord[1] + 12, chord[2] + 12], 0.09, 0.42 * vel, dk=3.0, decay=0.2, rel=0.12), t)
            put(b, clap(0.35 * vel, seed=3), t)
            put(b, hat(0.28 * vel, seed=4), t)
            return
        put(b, kick(1.0 * vel, seed=1), t)
        put(b, perc(GIANT, 0.55 * vel), t)
        put(b, sine(root - 12, 0.32 if kind == 'M' else 1.1, 0.42 * vel, rel=0.2, decay=0.5 if kind == 'M' else 1.0), t)
        if kind == 'M':
            put(b, stab(chord[:3] + ([top] if top else []), 0.30, 0.55 * vel, dk=1.6, decay=0.45, rel=0.2), t)
            put(b, hat(0.25 * vel, decay=0.06, seed=5), t)
        else:
            c = chord + ([top] if top else [])
            put(b, stab(c, final_len, 0.62 * vel, dk=0.55, decay=1.5, rel=0.8, voices=4, detune=14), t)
            put(b, stab([m + 12 for m in chord[1:4]], final_len, 0.16 * vel, dk=0.2, decay=2.4, rel=1.0, voices=4, detune=18, kmax=14,
                        seed=9), t + 0.02)                                   # nappe qui tient
            put(b, clap(0.6 * vel, seed=6, tail=0.25 if big else 0.12), t)
            if big:
                put(b, boom(0.55 * vel), t)
                put(b, perc(CRASH, 0.35 * vel), t)
        return
    # forge
    if kind == 'dit':
        put(b, anvil(0.95 * vel), t, p=0.12)
        put(b, perc(TENOR, 0.45 * vel), t, p=-0.15)
        put(b, note('cello-spic', root + 12, 0.75 * vel), t)
        put(b, note('tbn-stac', root + 12, 0.6 * vel), t, p=-0.2)
        return
    put(b, perc(GIANT, 0.9 * vel), t)
    put(b, perc(BDRUM, 0.45 * vel), t)
    put(b, timp(root, 0.6 * vel), t)
    put(b, kick(0.45 * vel, click=0.12, seed=2), t)
    for m, k, g, p in ((root, 'tuba-stac', 0.75, 0.0), (root + 12, 'tbn-stac', 0.8, -0.25), (chord[1] + 12, 'tbn-stac', 0.7, 0.25),
                       (root + 24, 'horn-stac', 0.75, -0.1), (top or chord[2] + 12, 'horn-stac', 0.7, 0.15)):
        put(b, note(k, m, g * vel), t, p=p)
    put(b, note('cb-spic', root, 0.85 * vel), t)
    put(b, note('cello-spic', root + 12, 0.8 * vel), t)
    if kind == 'A' and not big:
        put(b, perc(CRASH, 0.15 * vel), t)
    if kind == 'A' and big:
        put(b, perc(GONG, 0.5 * vel), t)
        put(b, perc(CRASH, 0.3 * vel), t)
        put(b, boom(0.45 * vel), t)
        for m, k, g, p in ((root, 'cello', 0.7, -0.3), (chord[1], 'cello', 0.6, -0.1), (chord[2], 'viola', 0.6, 0.1),
                           (chord[3], 'violin', 0.5, 0.25), (top or chord[4], 'violin', 0.5, 0.35)):
            put(b, note(k, m, g * vel, final_len, 1.2), t + 0.01, p=p)
        for m, p in ((chord[1] + 12, -0.2), (top or chord[2] + 12, 0.2)):
            put(b, note('horn', m, 0.55 * vel, final_len * 0.8, 1.0), t + 0.02, p=p)


def code(b, t0, chords=('D', 'D', 'C', 'D'), tops=(62, 62, None, 64), vel=1.0, speed=1.0, final_len=2.6, big=True):
    """Le motif complet, mesure commençant à t0 (speed 2 = deux fois plus vite)."""
    for (st, ln, kind), c, tp in zip(CODE, chords, tops):
        frappe(b, t0 + st * S16 / speed, kind, CH[c], vel, tp, final_len, big)


REP = {'bpm': BPM, 'mesure': BAR}

# --- 1. Indicatif d'ouverture -------------------------------------------------------------------------------------------
b = bus_of(8.0)
T1 = 1.2                                          # premier coup du code
if TEL:
    put(b, riser(1.25, 300, 9000, vel=0.32), T1 - 1.25)
    beeps, _ = morse('MA', unit=0.055, f=880.0, vel=0.42)
    put(b, beeps, 0.16)
    put(b, echo(beeps, 0.1375, fb=0.28, n=3, lp=2600, dry=0.0) * 0.5, 0.16)
    for k in range(16):                           # le téléscripteur se met en marche sous le code
        put(b, ticker(0.18 + 0.1 * (k % 4 == 0), seed=k), T1 + k * S16, p=(-0.35, 0.35)[k % 2])
        put(b, hat(0.12 + 0.08 * (k % 2), seed=20 + k), T1 + k * S16, p=0.2)
else:
    roll = perc(TIMP_ROLL, 0.7, 0.6)[: int(1.25 * SR)]
    roll = roll * (np.linspace(0.1, 1.0, len(roll)) ** 1.8)[:, None]
    put(b, fade(roll, 0.05, 0.03), T1 - 1.22)
    tr = note('cello-trem', 50, 0.6, 1.1, 0.1)
    put(b, tr * (np.linspace(0.05, 1.0, len(tr)) ** 2)[:, None], T1 - 1.15)
    for k in range(3):                            # trois coups de caisse qui annoncent le code
        put(b, perc(TENOR, 0.3 + 0.12 * k), T1 - (3 - k) * S16, p=(-0.2, 0.0, 0.2)[k])
put(b, perc(SWELL, 0.45), T1 - 1.15)
code(b, T1, final_len=2.8)
REP['intro_voix'] = round(T1 + BAR + 0.15, 3)          # la voix entre sur le premier temps de la mesure suivante
REP['intro_fond'] = round(T1 + BAR, 3)                 # le fond démarre en mesure, juste là
intro = finish(b[: int(6.8 * SR)], 'intro', -15.5, wet=-14, fout=1.4)

# --- 2. Carillon des nouvelles : la lettre A (· —) ----------------------------------------------------------------------
b = bus_of(2.0)
if TEL:
    beeps, seq = morse('A', unit=0.06, f=880.0, vel=0.5)
    put(b, beeps, 0.02)
    put(b, ticker(0.3, seed=40), 0.02)
    put(b, bell(1760.0, 0.9, 0.22), 0.02 + seq[1][0], p=0.2)
    put(b, kick(0.35, f_hi=120, decay=0.2, click=0.1, seed=41), 0.02 + seq[1][0])
else:
    put(b, anvil(0.7), 0.02, p=0.1)
    put(b, note('glock', 93, 0.6, 0.4, 0.8), 0.02 + 2 * S16 * 0.5, p=-0.1)
    put(b, note('marimba', 69, 0.6, 0.3, 0.5), 0.02 + 2 * S16 * 0.5)
    put(b, timp(38, 0.35), 0.02 + 2 * S16 * 0.5)
REP['carillon_voix'] = 0.55
carillon = finish(b[: int(1.5 * SR)], 'carillon', -19, wet=-15, fout=0.5)

# --- 3. Virgule entre deux rubriques : le code en accéléré --------------------------------------------------------------
b = bus_of(3.0)
code(b, 0.03, vel=0.75, speed=2.0, tops=(62, 62, None, 62), final_len=0.6, big=False)
REP['virgule_voix'] = round(0.03 + 12 * S16 / 2.0 + 0.3, 3)       # la voix repart juste après la dernière frappe
virgule = finish(b[: int(2.1 * SR)], 'virgule', -20, wet=-15, fout=0.8)

# --- 4. Souvenir de salle : le code au loin, sur une vieille radio --------------------------------------------------------
b = bus_of(5.0)
if TEL:
    beeps, _ = morse('MA', unit=0.07, f=740.0, vel=0.45)
    far = echo(vieille_radio(beeps), 0.255, fb=0.42, n=4, lp=2400)
    put(b, far, 0.05)
    put(b, crackle(3.6, vel=0.05), 0.0)
else:
    put(b, perc('Percussion/gongscrape_mf.wav', 0.35), 0.0)
    a = echo(anvil(0.5), 0.3, fb=0.45, n=4, lp=2600)
    put(b, a, 0.1, p=0.3)
put(b, perc(SWELL, 0.3), 0.15)
TS = 1.15
for i, m in enumerate([47, 54, 59, 62]):           # si mineur, posé au piano, avec le pleurage d'une vieille bande
    put(b, wow(note('piano', m, 0.48 - 0.04 * i, 2.0, 1.0)), TS + i * 0.03, p=-0.2 + 0.13 * i)
cel = note('cello', 47, 0.55, 2.4, 1.2)
put(b, cel * np.minimum(1.0, np.linspace(0.2, 1.6, len(cel)))[:, None], TS)
put(b, kick(0.4, f_hi=90, f_lo=40, decay=0.4, click=0.0, seed=50) if TEL else perc(GIANT_SOFT, 0.5), TS)
REP['souvenir_voix'] = round(TS + 0.5, 3)
REP['souvenir_fond'] = round(TS, 3)
souvenir = finish(b[: int(3.9 * SR)], 'souvenir', -21, wet=-12, fout=1.3)

# --- 5. Indicatif de fin : le code qui se pose sur ré ---------------------------------------------------------------------
b = bus_of(8.0)
code(b, 0.02, tops=(62, 62, None, 62), vel=0.95, final_len=3.0)
if TEL:
    beeps, _ = morse('MA', unit=0.055, f=880.0, vel=0.2)
    put(b, echo(beeps, 0.1375, fb=0.35, n=4, lp=2200), 0.02 + BAR + 0.55)
else:
    put(b, echo(anvil(0.35), 0.25, fb=0.4, n=3, lp=3000), 0.02 + BAR + 0.6, p=0.2)
REP['fin_attaque'] = 0.02
fin = finish(b[: int(6.4 * SR)], 'fin', -16.5, wet=-13, fout=2.2)


# --- 6. Les fonds (boucles sans couture, en mesure) -------------------------------------------------------------------------
def fond(bars, prog, intensity='fond'):
    L = bars * BAR
    b = bus_of(L + 3.0)
    for bar in range(bars):
        t0 = bar * BAR
        c = CH[prog[bar % len(prog)]]
        root = c[0]
        for st, ln, kind in CODE:                    # la pulsation du code, à chaque mesure
            t = t0 + st * S16
            if TEL:
                put(b, kick(0.5 if kind != 'dit' else 0.3, click=0.12, decay=0.26, seed=bar * 4 + st), t)
                if kind == 'dit':
                    put(b, ticker(0.35, seed=bar), t, p=0.3)
            else:
                put(b, perc(GIANT_SOFT, 0.55 if kind != 'dit' else 0.32), t)
                put(b, note('cb-spic', root, 0.55 if kind != 'dit' else 0.4), t)
        if TEL:
            for st in (4, 12):
                put(b, clap(0.2, seed=bar * 2 + st, tail=0.1), t0 + st * S16)
        for k in range(16):                          # le téléscripteur (ou les cordes) en doubles croches
            t = t0 + k * S16
            if TEL:
                acc = (0.16, 0.07, 0.11, 0.07)[k % 4] * (1.25 if intensity == 'ecrans' else 1.0)
                put(b, hat(acc, decay=0.02 + 0.01 * (k % 4 == 2), seed=bar * 16 + k), t, p=0.25)
                if intensity == 'ecrans' or k % 2 == 0:
                    put(b, ticker(0.07 + 0.04 * (k % 4 == 0), seed=500 + bar * 16 + k), t, p=-0.3)
            elif intensity == 'ecrans' or k % 2 == 0:
                put(b, note('violin-spic' if intensity == 'ecrans' else 'cello-spic',
                            (root + 24 if intensity == 'ecrans' else root + 12) + (7 if k % 8 == 6 else 0),
                            (0.42, 0.25, 0.33, 0.25)[k % 4]), t, p=(-0.25, 0.25)[k % 2])
        if TEL and intensity == 'fond':
            put(b, hat(0.1, decay=0.12, dur=0.3, seed=900 + bar), t0 + 14 * S16, p=-0.2)   # charleston ouvert
        # basse en croches (le moteur), avec un accent sur les coups du code
        for k in range(8 if intensity == 'fond' else 16):
            step = k * (2 if intensity == 'fond' else 1)
            t = t0 + step * S16
            accent = 1.0 if step in (0, 4, 10, 12) else 0.72
            if TEL:
                put(b, saw(root, S16 * (1.6 if intensity == 'fond' else 0.85), 0.34 * accent, rel=0.04, voices=2, detune=6,
                           kmax=30, dk=2.2, decay=0.25, seed=bar * 16 + k), t)
                put(b, sine(root - 12, S16 * (1.5 if intensity == 'fond' else 0.8), 0.25 * accent, rel=0.04), t)
        if intensity == 'fond':
            if bar % 2 == 0:                         # nappe (synthé ou cor) : la couleur de l'accord, très bas
                if TEL:
                    put(b, stab([c[1] + 12, c[2] + 12, c[3] + 12], 2 * BAR - 0.3, 0.13, dk=0.0, decay=None, rel=0.6, voices=4,
                                detune=16, kmax=10, seed=bar), t0 + 0.02)
                else:
                    for m, p in ((c[1], -0.2), (c[2], 0.2)):
                        put(b, note('horn', m, 0.32, 2 * BAR - 0.4, 0.8), t0 + 0.03, p=p)
            if TEL:                                  # arpège pincé, en écho : l'étincelle
                arp = [c[4] + 12, c[2] + 12, c[3] + 12, c[2] + 12]
                for k in range(8):
                    if (bar % 2 == 1 and k >= 6):
                        continue
                    put(b, echo(saw(arp[k % 4], 0.12, 0.09, rel=0.12, voices=2, detune=7, kmax=24, dk=5.0, decay=0.18,
                                    seed=bar * 8 + k), 0.375, fb=0.3, n=2, lp=3800), t0 + 2 * k * S16, p=(-0.4, 0.4)[k % 2])
            if bar % 4 == 3:                         # l'enclume, toutes les quatre mesures, sur la brève
                put(b, anvil(0.28), t0 + 10 * S16, p=0.35)
            if not TEL and bar == bars - 1:          # roulement de timbale qui relance la boucle
                roll = perc(TIMP_ROLL, 0.35, 0.6)[: int(BAR / 2 * SR)]
                put(b, fade(roll * np.linspace(0.1, 1, len(roll))[:, None] ** 2, 0.05, 0.05), t0 + BAR / 2)
        elif intensity == 'ecrans' and bar % 2 == 1:
            put(b, anvil(0.22), t0 + 10 * S16, p=0.35)
    if intensity == 'ecrans':                        # bourdon grave sous les nouvelles
        put(b, (stab([38, 45], L, 0.12, dk=0.0, decay=None, rel=0.5, voices=3, detune=10, kmax=12) if TEL
                else note('cello', 38, 0.35, L, 0.5)), 0.0)
    return b, L


bf, L = fond(8, PROG, 'fond')
fond_ = finish(bf, 'fond', -28, wet=-16, loop=L, mids=-4.0)
be, Le = fond(4, ['D'], 'ecrans')
fond_ecrans = finish(be, 'fond-ecrans', -29, wet=-17, loop=Le, mids=-5.0)

# Fond du souvenir : la moitié du tempo, piano et cordes de mémoire, un battement de cœur sur le code
bs = bus_of(4 * BAR * 2 + 3.0)
for i, c in enumerate([[35, 42, 47, 50, 54], [31, 38, 43, 47, 50], [38, 45, 50, 54, 57], [33, 40, 45, 49, 52]]):  # si m, sol, ré, la
    t0 = i * 2 * BAR
    put(bs, note('cello', c[0], 0.3, 2 * BAR - 0.2, 0.9), t0, p=-0.2)
    put(bs, note('viola', c[2], 0.26, 2 * BAR - 0.2, 0.9), t0, p=0.2)
    for k, m in enumerate([c[1] + 12, c[2] + 12, c[3] + 12, c[4] + 12]):
        put(bs, wow(note('piano', m, 0.22, 0.9, 0.8), seed=i * 4 + k), t0 + k * BEAT * 2, p=(-0.3, -0.1, 0.1, 0.3)[k])
    for st, ln, kind in CODE:
        t = t0 + st * S16 * 2
        put(bs, (kick(0.3 if kind != 'dit' else 0.18, f_hi=85, f_lo=40, decay=0.35, click=0.0, seed=i * 16 + st) if TEL
                 else perc(GIANT_SOFT, 0.3 if kind != 'dit' else 0.18)), t)
if TEL:
    put(bs, crackle(4 * BAR * 2 + 2.0, density=10, vel=0.025, seed=77), 0.0)
fond_souvenir = finish(bs, 'fond-souvenir', -30, wet=-12, loop=4 * BAR * 2, mids=-3.0)

REP.update({'style': STYLE, 'fichiers': ['intro', 'carillon', 'virgule', 'souvenir', 'fin', 'fond', 'fond-ecrans', 'fond-souvenir'],
            'effacement_fond_db': -10})
json.dump(REP, open(os.path.join(OUT, 'reperes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(REP, ensure_ascii=False))

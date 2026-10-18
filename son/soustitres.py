"""Sous-titres WebVTT du film à partir du découpage (plan.js) et du texte (texte.json).
Une phrase longue est coupée à ses points (au prorata des caractères) ; 42 caractères par ligne au plus, 2 lignes."""
import json, re, sys, textwrap

PLAN, TEXTE, OUT = sys.argv[1:4]
LANG = sys.argv[4] if len(sys.argv) > 4 else 'fr'
p = json.loads(open(PLAN).read().replace('window.__plan = ', '').rstrip().rstrip(';'))
T = json.load(open(TEXTE, encoding='utf-8'))
txt = {l['id']: l['text'] for a in T['acts'] for l in a['lines']}


SMALL = {'de', 'à', 'la', 'le', 'les', 'un', 'une', 'des', 'il', 'et', 'qui', 'que', 'vous', 'sur', 'pour', 'du', 'ses', 'son', 'sa',
         'vos', 'votre', 'leurs', 'leur', 'au', 'aux', 'en', 'ne', 'pas', 'plus', "d'or,", 'avec', 'par', 'face', 'se', 'même', 'est'}
# mêmes règles en anglais et en espagnol
SMALL |= {'the', 'a', 'an', 'to', 'of', 'and', 'in', 'on', 'your', 'its', 'it', 'you', 'with', 'by', 'for', 'at',
          'el', 'los', 'las', 'una', 'y', 'su', 'sus', 'por', 'con', 'lo', 'del', 'al', 'sin'}


def wrap2(g, width=42):
    """Deux lignes équilibrées ; espace insécable devant ! ? : ; (typographie française)."""
    if LANG == 'fr':
        g = re.sub(r' ([!?:;»])', '\u00a0\\1', g)
    if len(g) <= width:
        return g
    words = g.split(' ')
    best = None
    for k in range(1, len(words)):
        l1, l2 = ' '.join(words[:k]), ' '.join(words[k:])
        sc = max(len(l1), len(l2)) + (100 if max(len(l1), len(l2)) > width else 0)
        if re.search(r'[.,…?!:;]$', l1):
            sc -= 9  # couper après une ponctuation
        if words[k - 1].lower() in SMALL:
            sc += 7  # jamais après un petit mot (article, préposition, pronom)
        if best is None or sc < best[0]:
            best = (sc, l1 + '\n' + l2)
    return best[1]


def ts(t):
    h, r = divmod(max(0.0, t), 3600); m, s = divmod(r, 60)
    return f'{int(h):02d}:{int(m):02d}:{s:06.3f}'


cues = []
for sh in p['shots']:
    s = txt[sh['id']]
    a, b = sh['lineStart'], sh['lineEnd'] + 0.25
    parts = [x.strip() for x in re.split(r'(?<=[.!?])\s+', s) if x.strip()]
    # regrouper les morceaux pour que chaque sous-titre tienne sur 2 lignes de 42 caractères
    # deux phrases courtes partagent un sous-titre (une par ligne) ; une phrase longue a le sien
    groups, cur, n = [], '', 0
    for x in parts:
        if cur and (n >= 2 or len(cur) > 42 or len(x) > 42):
            groups.append(cur); cur, n = x, 1
        else:
            cur, n = (cur + ' ' + x).strip(), n + 1
    groups.append(cur)
    total = sum(len(g) for g in groups); t = a
    for g in groups:
        d = (b - a) * len(g) / total
        cues.append((t, t + d - (0.04 if g is not groups[-1] else 0), wrap2(g)))
        t += d
out = ['WEBVTT', '']
for k, (a, b, g) in enumerate(cues, 1):
    out += [str(k), f'{ts(a)} --> {ts(b)}', g, '']
open(OUT, 'w', encoding='utf-8').write('\n'.join(out))
print('\n'.join(out[:30]))
print('…', len(cues), 'sous-titres')

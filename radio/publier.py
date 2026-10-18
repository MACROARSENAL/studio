"""Met une émission fabriquée à l'antenne du terminal MACROARSENAL (onglet Radio et lecteur du terminal).

Usage : python radio/publier.py <émission.json> <dossier des sons>
        (le dossier de l'émission sur la branche « emissions » : <id>-<langue>.mp3 et <id>-<langue>-minutage.json)
        python radio/publier.py --verifier   (contrôle des secrets et de l'accès à Supabase, sans rien publier)
Variables : SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY (secrets du dépôt). Sans elles, rien n'est publié (simple avis).

- Le MP3 de chaque langue fabriquée part dans le stockage Supabase (dossier public « radio »), sous un nom propre à
  cette version : une émission corrigée ne risque jamais d'être servie dans son ancienne version.
- La fiche de l'émission (titre, résumé, texte lu, son, durée) est écrite dans market_stats « radio », que lit le site.
- Heure de sortie : 8 h à Paris le jour de l'émission (ou site.sortie). Une émission rangée d'avance n'apparaît qu'à son heure.
- Durée de vie (décision de Kévin, 18/10/2026) : la matinale reste à l'antenne jusqu'à la sortie de la suivante, puis elle
  est supprimée. Le site n'affiche que la dernière matinale sortie ; ici, on retire les fiches et les sons des précédentes.
- Ordre sûr : envoi des sons, puis fiche, puis ménage. Le site ne pointe jamais vers un son effacé.
"""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LANGS = ('fr', 'en', 'es')
URL = (os.environ.get('SUPABASE_URL') or '').strip().rstrip('/')
KEY = (os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or '').strip()
ICI = os.path.dirname(os.path.abspath(__file__))
PUBLIC = '/storage/v1/object/public/radio/'


def note(level, msg):
    print(msg)
    if os.environ.get('GITHUB_ACTIONS'):
        print(f"::{level} title=Mise à l'antenne::" + msg.replace('%', '%25').replace('\r', ' ').replace('\n', ' '))


class Refus(Exception):
    pass


def appel(method, path, body=None, headers=None, accepte=()):
    """Requête vers Supabase. Renvoie (code, contenu) ; une réponse en erreur non prévue arrête tout."""
    h = {'apikey': KEY, **({'Authorization': 'Bearer ' + KEY} if KEY.startswith('eyJ') else {}), **(headers or {})}
    data = body if body is None or isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
    if data is not None and 'Content-Type' not in h:
        h['Content-Type'] = 'application/json'
    r = urllib.request.Request(URL + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=90) as res:
            raw = res.read()
            ct = res.headers.get('content-type', '')
            return res.status, (json.loads(raw) if raw and ct.startswith('application/json') else raw)
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', 'replace')[:400]
        if e.code in accepte:
            return e.code, txt
        raise Refus(f"{method} {path.split('?')[0]} : HTTP {e.code} {txt}")


def iso(dt):
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def instant(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def nom_objet(url):
    return url.split(PUBLIC, 1)[1] if PUBLIC in url else None


def verifier():
    """Contrôle des secrets, sans rien publier ni rien créer : lecture du dossier « radio » du stockage et de la fiche
    market_stats « radio ». Sert une fois les secrets rangés (Kévin, 18/10/2026), avant le redémarrage de la radio."""
    if not URL or not KEY:
        manque = [n for n, v in (('SUPABASE_URL', URL), ('SUPABASE_SERVICE_ROLE_KEY', KEY)) if not v]
        raise Refus(f"secret(s) absent(s) du dépôt : {', '.join(manque)}")
    code, _ = appel('GET', '/storage/v1/bucket/radio', accepte=(400, 404))
    dossier = 'présent' if code == 200 else 'absent (il sera créé à la première mise à l\'antenne)'
    _, rows = appel('GET', '/rest/v1/market_stats?select=id,updated_at&id=eq.radio')
    fiche = f"présente (mise à jour le {rows[0]['updated_at'][:10]})" if rows else 'aucune pour l\'instant'
    note('notice', f"Connexion à Supabase réussie. Stockage accessible : dossier « radio » {dossier}. "
                   f"Base accessible : fiche « radio » {fiche}. Rien n'a été publié.")


def main():
    if sys.argv[1:2] == ['--verifier']:
        return verifier()
    emi, dossier = sys.argv[1:3]
    E = json.load(open(emi, encoding='utf-8'))
    S = E.get('site') or {}
    ID, jour = E['id'], E['date']
    genre = S.get('genre', 'matinale')
    if S.get('sortie'):
        sortie = iso(instant(S['sortie']))
    else:
        y, m, d = map(int, jour.split('-'))
        sortie = iso(datetime(y, m, d, 8, 0, tzinfo=ZoneInfo('Europe/Paris')))

    sons = {}
    for l in LANGS:
        mp3 = os.path.join(dossier, f'{ID}-{l}.mp3')
        if os.path.exists(mp3):
            mn = os.path.join(dossier, f'{ID}-{l}-minutage.json')
            sec = json.load(open(mn, encoding='utf-8'))['seconds'] if os.path.exists(mn) else None
            data = open(mp3, 'rb').read()
            sons[l] = (data, sec, hashlib.sha1(data).hexdigest()[:10])
    if not sons:
        raise Refus(f'aucun son dans {dossier} (attendu : {ID}-fr.mp3, {ID}-en.mp3 ou {ID}-es.mp3)')
    manque = [l for l in sons if not (S.get('titre') or {}).get(l) or not (S.get('resume') or {}).get(l)]
    if manque:
        raise Refus(f"titre ou résumé manquant dans « site » pour : {', '.join(manque)}")
    if any(sec is None for _, sec, _ in sons.values()):
        raise Refus('minutage manquant : durée inconnue')

    antenne = json.load(open(os.path.join(ICI, 'antenne.json'), encoding='utf-8'))
    texte = {l: ' '.join(b['texte'].strip() for b in E['blocs'].get(l, [])) for l in LANGS}
    fiche = {
        'id': ID, 'kind': genre, 'day': jour, 'publishedAt': sortie,
        'title': {l: (S.get('titre') or {}).get(l, '') for l in LANGS},
        'summary': {l: (S.get('resume') or {}).get(l, '') for l in LANGS},
        'script': texte,
        'audio': {}, 'duration': {l: round(sec) for l, (_, sec, _) in sons.items()},
        'hash': hashlib.sha1('|'.join(h for _, _, h in sons.values()).encode()).hexdigest()[:10],
    }
    hp = instant(sortie).astimezone(ZoneInfo('Europe/Paris'))
    heure = f'{hp.day:02d}/{hp.month:02d} à {hp.hour} h {hp.minute:02d}'
    resume = ', '.join(f'{l} {divmod(round(sec), 60)[0]} min {divmod(round(sec), 60)[1]:02d}' for l, (_, sec, _) in sons.items())

    if not URL or not KEY:
        note('warning', f'{ID} prêt mais non publié : secrets SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY absents du dépôt '
                        f'(sortie prévue le {heure}, heure de Paris ; {resume}).')
        return

    # 1. sons
    code, _ = appel('GET', '/storage/v1/bucket/radio', accepte=(400, 404))
    if code != 200:
        appel('POST', '/storage/v1/bucket', {'id': 'radio', 'name': 'radio', 'public': True, 'allowed_mime_types': ['audio/mpeg'],
                                             'file_size_limit': 20 * 1024 * 1024}, accepte=(409,))
    for l, (data, _, h) in sons.items():
        nom = f'{ID}-{l}-{h}.mp3'
        appel('POST', f'/storage/v1/object/radio/{nom}', data,
              {'Content-Type': 'audio/mpeg', 'x-upsert': 'true', 'cache-control': 'max-age=31536000'})
        fiche['audio'][l] = URL + PUBLIC + nom
        # le son doit être lisible publiquement avant d'être annoncé
        with urllib.request.urlopen(urllib.request.Request(fiche['audio'][l], method='HEAD'), timeout=60) as r:
            if r.status != 200 or 'audio' not in r.headers.get('content-type', ''):
                raise Refus(f"{nom} n'est pas servi comme un son (HTTP {r.status}, {r.headers.get('content-type')})")

    # 2. fiche (et durée de vie des matinales)
    _, rows = appel('GET', '/rest/v1/market_stats?select=data&id=eq.radio')
    prev = rows[0]['data'] if rows else None
    avant = list((prev or {}).get('episodes', []))
    ancienne = next((x for x in avant if x.get('id') == ID), None)
    eps = [x for x in avant if x.get('id') != ID] + [fiche]
    maintenant = instant(os.environ['RADIO_MAINTENANT']) if os.environ.get('RADIO_MAINTENANT') else datetime.now(timezone.utc)  # essais
    mats = sorted((x for x in eps if x.get('kind') == 'matinale'), key=lambda x: instant(x['publishedAt']))
    sorties = [x for x in mats if instant(x['publishedAt']) <= maintenant]
    retirees = [x for x in mats if sorties and instant(x['publishedAt']) < instant(sorties[-1]['publishedAt'])]
    eps = sorted((x for x in eps if x not in retirees), key=lambda x: x['publishedAt'], reverse=True)
    data = {'host': antenne['animateur'], 'updatedAt': iso(maintenant), 'episodes': eps}
    appel('POST', '/rest/v1/market_stats?on_conflict=id', [{'id': 'radio', 'data': data, 'updated_at': iso(maintenant)}],
          {'Prefer': 'resolution=merge-duplicates,return=minimal'})

    # 3. ménage : sons des matinales retirées et de l'ancienne version de cette émission
    gardes = {nom_objet(u) for x in eps for u in (x.get('audio') or {}).values()}
    effaces = sorted({n for x in retirees + ([ancienne] if ancienne else []) for u in (x.get('audio') or {}).values()
                      if (n := nom_objet(u)) and n not in gardes})
    if effaces:
        appel('DELETE', '/storage/v1/object/radio', {'prefixes': effaces})

    note('notice', f"{ID} à l'antenne le {heure} (heure de Paris) : {resume}. "
                   f"{len(retirees)} matinale(s) retirée(s), {len(effaces)} son(s) effacé(s), {len(eps)} émission(s) en ligne.")


if __name__ == '__main__':
    try:
        main()
    except (Refus, urllib.error.URLError, KeyError, ValueError) as e:
        note('error', f'Échec : {e}')
        sys.exit(1)

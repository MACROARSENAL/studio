import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

/**
 * Doji en peluche (17/10/2026, demande de Kévin : une peluche stylée, de qualité et réconfortante pour le shop).
 * Même silhouette que le personnage (bouclier du logo, chandelle-antenne et étoile, corps-œuf), en tissus :
 * minky marine et ivoire, velours pour la visière, passepoil satin or, yeux-chandelles et sourire brodés, étoile matelassée,
 * coutures visibles et étiquette cousue. Rendu photo de produit, studio doux.
 * Réglages par l'adresse : ?vue=34|face|dos|detail&fond=clair|nuit&w=1600&h=2000
 */
const Q = new URLSearchParams(location.search);
const VUE = Q.get('vue') ?? '34';
const FOND = Q.get('fond') ?? 'clair';
const W = Number(Q.get('w') ?? 1600), H = Number(Q.get('h') ?? 2000);
const S = 0.01;

// --- Le bouclier du logo (mêmes cotes que le personnage) ----------------------------------------------------------------
const L2 = (x: number, y: number) => new THREE.Vector2((x - 100) * S * 0.62, -(y - 120) * S * 0.62);
function shieldShape(): THREE.Shape {
  const s = new THREE.Shape();
  const a = L2(10, 20); s.moveTo(a.x, a.y);
  const b = L2(190, 20); s.lineTo(b.x, b.y);
  const c = L2(190, 118); s.lineTo(c.x, c.y);
  const c1 = L2(190, 176), c2 = L2(150, 212), e = L2(100, 234); s.bezierCurveTo(c1.x, c1.y, c2.x, c2.y, e.x, e.y);
  const d1 = L2(50, 212), d2 = L2(10, 176), f = L2(10, 118); s.bezierCurveTo(d1.x, d1.y, d2.x, d2.y, f.x, f.y);
  s.lineTo(a.x, a.y);
  return s;
}
function makeRadius(smooth = 26) {
  const pts = shieldShape().getSpacedPoints(900);
  let minY = Infinity, maxY = -Infinity;
  for (const p of pts) { minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y); }
  const cy = (minY + maxY) / 2;
  const samples = pts.map((p) => ({ a: Math.atan2(p.y - cy, p.x), r: Math.hypot(p.x, p.y - cy) })).sort((u, v) => u.a - v.a);
  const N = 1440; const raw = new Float32Array(N);
  const first = samples[0], lastS = samples[samples.length - 1];
  for (let i = 0; i < N; i++) {
    const th = -Math.PI + (i / N) * Math.PI * 2;
    if (th <= first.a || th >= lastS.a) { raw[i] = (first.r + lastS.r) / 2; continue; }
    let lo = 0, hi = samples.length - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (samples[mid].a <= th) lo = mid; else hi = mid; }
    const A = samples[lo], B = samples[hi]; const k = B.a === A.a ? 0 : (th - A.a) / (B.a - A.a);
    raw[i] = A.r + (B.r - A.r) * k;
  }
  // Coins bien plus doux que sur le personnage : une peluche n'a pas d'angle
  const R = new Float32Array(N);
  for (let i = 0; i < N; i++) { let s = 0; for (let j = -smooth; j <= smooth; j++) s += raw[(i + j + N) % N]; R[i] = s / (2 * smooth + 1); }
  const at = (th: number) => { let u = ((th + Math.PI) / (Math.PI * 2)) * N; u = ((u % N) + N) % N; const i = Math.floor(u), f = u - i; return R[i] * (1 - f) + R[(i + 1) % N] * f; };
  return { cy, at };
}
/** Coussin : deux panneaux (avant, arrière) cousus sur le pourtour ; le léger pincement de la couture est conservé. */
function pillow(radius: (th: number) => number, cy: number, depth: number, E: number, pinch = 0.06, segU = 240, segV = 120) {
  const pos: number[] = []; const idx: number[] = [];
  for (let j = 0; j <= segV; j++) {
    const phi = (j / segV) * Math.PI; const sp = Math.sin(phi), cp = Math.cos(phi);
    const rr = Math.pow(Math.max(0, sp), E); let zz = Math.sign(cp) * Math.pow(Math.abs(cp), E) * depth;
    const seam = Math.exp(-Math.pow(Math.abs(cp) / 0.08, 2)); // creux de couture le long du bord
    const k = 1 - pinch * seam;
    zz *= 1;
    for (let i = 0; i <= segU; i++) {
      const th = (i / segU) * Math.PI * 2; const R = radius(th) * k;
      pos.push(Math.cos(th) * rr * R, cy + Math.sin(th) * rr * R, zz);
    }
  }
  for (let j = 0; j < segV; j++) for (let i = 0; i < segU; i++) { const a = j * (segU + 1) + i, b = a + segU + 1; idx.push(a, b, a + 1, b, b + 1, a + 1); }
  let g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
  g = mergeVertices(g, 1e-6); g.computeVertexNormals();
  // UV planes (pour le grain du tissu)
  g.computeBoundingBox(); const bb = g.boundingBox!; const p = g.attributes.position; const uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) { uv[i * 2] = (p.getX(i) - bb.min.x) / (bb.max.x - bb.min.x) * 3; uv[i * 2 + 1] = (p.getY(i) - bb.min.y) / (bb.max.y - bb.min.y) * 3.6 + (p.getZ(i) < 0 ? 5 : 0); }
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  return g;
}

// --- Textures de tissu, dessinées en code ---------------------------------------------------------------------------------
function canvasTex(w: number, h: number, draw: (g: CanvasRenderingContext2D) => void, repeat = true) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d')!; draw(g);
  const t = new THREE.CanvasTexture(c); if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; } t.anisotropy = 8; return t;
}
let seed = 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
/** Poils du minky : myriade de petites mèches orientées, en relief (bumpMap). */
const pile = canvasTex(1024, 1024, (g) => {
  g.fillStyle = '#808080'; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 60000; i++) {
    const x = rnd() * 1024, y = rnd() * 1024, l = 2 + rnd() * 5, a = 1.2 + (rnd() - 0.5) * 0.9, v = Math.floor(90 + rnd() * 120);
    g.strokeStyle = `rgba(${v},${v},${v},0.55)`; g.lineWidth = 0.8 + rnd() * 0.8;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke();
  }
});
/** Point de satin (broderie) : fils parallèles serrés. */
const satin = (angle: number) => canvasTex(256, 256, (g) => {
  g.fillStyle = '#808080'; g.fillRect(0, 0, 256, 256); g.translate(128, 128); g.rotate(angle); g.translate(-256, -256);
  for (let x = 0; x < 512; x += 5) { const v = 150 + Math.floor(rnd() * 60); g.fillStyle = `rgb(${v},${v},${v})`; g.fillRect(x, 0, 3, 512); g.fillStyle = 'rgb(70,70,70)'; g.fillRect(x + 3, 0, 1.2, 512); }
});
const satinV = satin(0), satinD = satin(0.6);
/** Couleur des fils (léger contraste entre les brins), pour que la broderie se voie. */
const thread = (base: string, dark: string, angle: number, rep: number) => {
  const t = canvasTex(256, 256, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 256); g.translate(128, 128); g.rotate(angle); g.translate(-256, -256);
    for (let x = 0; x < 512; x += 5) { g.fillStyle = dark; g.globalAlpha = 0.35 + rnd() * 0.25; g.fillRect(x + 3, 0, 1.4, 512); } });
  t.colorSpace = THREE.SRGBColorSpace; t.repeat.set(rep, rep); return t;
};
satinV.repeat.set(1, 1); satinD.repeat.set(2, 2);

/** Fibres du minky vues de près : points serrés, plus ou moins longs (masque pour les couches de poils). */
const strands = canvasTex(512, 512, (g) => {
  g.fillStyle = '#000'; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 26000; i++) { const x = rnd() * 512, y = rnd() * 512, v = Math.floor(80 + rnd() * 175); g.fillStyle = `rgb(${v},${v},${v})`; g.beginPath(); g.arc(x, y, 0.7 + rnd() * 0.9, 0, Math.PI * 2); g.fill(); }
});

// --- Matières -------------------------------------------------------------------------------------------------------------
const minky = (color: number, sheen: number, bump = 0.9, rough = 0.9) => new THREE.MeshPhysicalMaterial({
  color, roughness: Math.max(rough, 0.95), metalness: 0, specularIntensity: 0.22, sheen: 1, sheenRoughness: 0.34, sheenColor: new THREE.Color(sheen), bumpMap: pile, bumpScale: bump,
});
const marine = minky(0x1d2233, 0xd2d9f2, 1.4);          // le bouclier : minky marine profond (le « noir Arsenal » en doux)
const visiere = minky(0x161a27, 0x8790ad, 0.9, 0.95);    // la visière : velours plus sombre
const ivoire = minky(0xf1eadc, 0xffffff, 1.4, 0.95);      // le corps : minky ivoire, tout doux
const orDoux = minky(0xd2a957, 0xffe7a6, 0.9, 0.8);       // étoile et capteurs : minky doré
const satinOr = new THREE.MeshPhysicalMaterial({ color: 0xd8b064, roughness: 0.36, metalness: 0.12, sheen: 0.7, sheenColor: new THREE.Color(0xfff0c4), sheenRoughness: 0.3, bumpMap: satinD, bumpScale: 0.6 });
const brodIvoire = new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: thread('#fbf5e8', '#b9ad96', 0, 1), roughness: 0.5, sheen: 0.7, sheenColor: new THREE.Color(0xffffff), bumpMap: satinV, bumpScale: 3 });
const brodOr = new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: thread('#e4bd66', '#8a6a24', 0.6, 2), roughness: 0.42, metalness: 0.12, sheen: 0.6, sheenColor: new THREE.Color(0xfff2c8), bumpMap: satinD, bumpScale: 2.5 });
const feutreRose = new THREE.MeshPhysicalMaterial({ color: 0xec8f8a, roughness: 1, sheen: 0.5, sheenColor: new THREE.Color(0xffd6d0), bumpMap: pile, bumpScale: 0.4 });
const couture = (color: number) => new THREE.MeshStandardMaterial({ color, roughness: 1 });

/** Poils : N couches légèrement décalées le long de la normale, dont seules les fibres restent (l'effet « peluche »). */
const furTargets: { mesh: THREE.Mesh; len: number; layers: number; rep: number }[] = [];
const fur = (mesh: THREE.Mesh, len = 2.4 * S, layers = 14, rep = 18) => { furTargets.push({ mesh, len, layers, rep }); return mesh; };
function growFur() {
  for (const { mesh, len, layers, rep } of furTargets) {
    const base = mesh.material as THREE.MeshPhysicalMaterial;
    for (let k = 1; k <= layers; k++) {
      const u = k / layers;
      const m = base.clone();
      m.alphaMap = strands.clone(); m.alphaMap.repeat.set(rep, rep); m.alphaMap.needsUpdate = true;
      m.alphaTest = 0.18 + 0.72 * u; m.transparent = false; m.bumpMap = null;
      m.color = base.color.clone().multiplyScalar(0.72 + 0.28 * Math.pow(u, 0.6)).lerp(new THREE.Color(0xffffff), base.color.getHSL({ h: 0, s: 0, l: 0 }).l < 0.2 ? 0.08 * u : 0); // racines plus sombres, pointes un peu claires sur le marine
      m.sheen = 1; m.sheenRoughness = 0.3 + 0.2 * u;
      const off = len * u;
      m.onBeforeCompile = (sh) => { sh.vertexShader = sh.vertexShader.replace('#include <begin_vertex>', `#include <begin_vertex>\n transformed += normalize(objectNormal) * ${off.toFixed(5)};`); };
      m.customProgramCacheKey = () => `fur${off.toFixed(5)}`;
      const shell = new THREE.Mesh(mesh.geometry, m); shell.castShadow = false; shell.receiveShadow = true; mesh.add(shell);
    }
  }
}

// --- La peluche -----------------------------------------------------------------------------------------------------------
const doji = new THREE.Group();
const { cy: CY, at: R } = makeRadius();
const DEPTH = 34 * S, E = 0.84;
const zFront = (s: number) => DEPTH * Math.pow(Math.max(0, 1 - Math.pow(Math.min(1, s), 2 / E)), E / 2);
const zFace = (x: number, y: number) => { const th = Math.atan2(y - CY, x); return zFront(Math.hypot(x, y - CY) / R(th)); };

// Tête
const head = new THREE.Group(); doji.add(head);
const headMesh = fur(new THREE.Mesh(pillow(R, CY, DEPTH, E), marine), 3.0 * S, 16, 24); head.add(headMesh);
// Couture du pourtour (avant / arrière) : un fin cordon à peine plus sombre
{
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i < 400; i++) { const th = (i / 400) * Math.PI * 2; const r = R(th) * 0.94; pts.push(new THREE.Vector3(Math.cos(th) * r, CY + Math.sin(th) * r, 0)); }
  head.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true), 600, 1.1 * S, 8, true), couture(0x11141c)));
}
// Visière en velours, cerclée d'un passepoil satin or
const SV = 0.8, LIFT = 0.8 * S;
{
  const rings = 50, segs = 260; const pos: number[] = [0, CY, zFront(0) + LIFT]; const idx: number[] = [];
  for (let k = 1; k <= rings; k++) { const s = SV * (k / rings); for (let i = 0; i < segs; i++) { const th = (i / segs) * Math.PI * 2; const r = s * R(th); const edge = Math.pow(k / rings, 8); pos.push(Math.cos(th) * r, CY + Math.sin(th) * r, zFront(s) + LIFT * (1 - edge * 0.9)); } }
  for (let i = 0; i < segs; i++) idx.push(0, 1 + i, 1 + ((i + 1) % segs));
  for (let k = 1; k < rings; k++) { const a0 = 1 + (k - 1) * segs, b0 = 1 + k * segs; for (let i = 0; i < segs; i++) { const i1 = (i + 1) % segs; idx.push(a0 + i, b0 + i, a0 + i1, b0 + i, b0 + i1, a0 + i1); } }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
  const uv: number[] = []; for (let i = 0; i < pos.length; i += 3) uv.push(pos[i] * 4, pos[i + 1] * 4); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals(); head.add(new THREE.Mesh(g, visiere));
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i < 360; i++) { const th = (i / 360) * Math.PI * 2; const r = SV * R(th); pts.push(new THREE.Vector3(Math.cos(th) * r, CY + Math.sin(th) * r, zFront(SV) + LIFT * 0.4)); }
  const tg = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true), 520, 2.9 * S, 18, true);
  head.add(new THREE.Mesh(tg, satinOr));
}
// Yeux-chandelles brodés, joues de feutre, sourire brodé or
const EYE_X = 24, EYE_Y = -5, EYE_W = 16.5, EYE_H = 27;
const onFace = (x: number, y: number, extra = 0) => zFace(x * S, y * S) + LIFT + extra;
for (const side of [-1, 1]) {
  const x = side * EYE_X;
  const eye = new THREE.Mesh(new RoundedBoxGeometry(EYE_W * S, EYE_H * S, 3.4 * S, 6, 5.5 * S), brodIvoire);
  eye.position.set(x * S, EYE_Y * S, onFace(x, EYE_Y, 0.2 * S)); eye.rotation.y = -Math.atan2(zFace((x + 2) * S, EYE_Y * S) - zFace((x - 2) * S, EYE_Y * S), 4 * S) * 0.9; head.add(eye);
  for (const dy of [1, -1]) {
    const wick = new THREE.Mesh(new THREE.CapsuleGeometry(1.25 * S, 5 * S, 6, 12), brodIvoire);
    const yy = EYE_Y + dy * (EYE_H / 2 + 4.2); wick.position.set(x * S, yy * S, onFace(x, yy, 0.3 * S)); head.add(wick);
  }
  const blush = new THREE.Mesh(new THREE.CylinderGeometry(6.4 * S, 6.4 * S, 1 * S, 40), feutreRose);
  blush.rotation.x = Math.PI / 2; blush.scale.set(1.25, 1, 0.75); const bx = side * 31, by = -25; blush.position.set(bx * S, by * S, onFace(bx, by, 0.1 * S));
  blush.rotation.y = side * 0.25; head.add(blush);
}
{
  const MY = -31;
  const smile = new THREE.Mesh(new THREE.TorusGeometry(8.4 * S, 2.1 * S, 14, 48, Math.PI * 0.82), brodOr);
  smile.rotation.z = Math.PI * 1.09; smile.scale.set(1, 1, 0.45); smile.position.set(0, MY * S, onFace(0, MY, 0.4 * S)); head.add(smile);
}
// Capteurs des flancs : pastilles de minky doré, matelassées
const HALF_W = R(0);
for (const side of [-1, 1]) {
  const prof = [[0, -4.6], [8, -4.6], [11.5, -3.6], [12.6, -1], [12.6, 1], [11.5, 3.6], [8, 4.6], [0, 4.6]].map(([r, y]) => new THREE.Vector2(r * S, y * S));
  const ear = fur(new THREE.Mesh(new THREE.LatheGeometry(new THREE.SplineCurve(prof).getPoints(40), 64), orDoux), 1.4 * S, 10, 6);
  ear.rotation.z = Math.PI / 2; ear.position.set(side * (HALF_W * 0.95 + 2 * S), 16 * S, 0); head.add(ear);
  const button = new THREE.Mesh(new THREE.SphereGeometry(5 * S, 32, 20), satinOr); button.scale.set(0.45, 1, 1);
  button.position.set(side * (HALF_W * 0.95 + 6.6 * S), 16 * S, 0); head.add(button);
}
// Antenne : la chandelle du logo en satin or rembourré, et l'étoile matelassée
{
  const topY = CY + R(Math.PI / 2) * 0.96;
  const ant = new THREE.Group(); ant.position.set(L2(138, 0).x, topY - 4 * S, 0); ant.rotation.z = -0.06; head.add(ant);
  const prof = [[0, -10], [7.8, -10], [8.6, -7], [8.6, 22], [8.2, 26], [6.6, 30], [3.8, 33], [0, 34]].map(([r, y]) => new THREE.Vector2(r * S, y * S));
  ant.add(new THREE.Mesh(new THREE.LatheGeometry(new THREE.SplineCurve(prof).getPoints(40), 64), satinOr));
  const ring = new THREE.Mesh(new THREE.TorusGeometry(8.4 * S, 2.2 * S, 14, 48), brodOr); ring.rotation.x = Math.PI / 2; ring.position.y = 2 * S; ant.add(ring);
  const st = new THREE.Shape();
  for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2 - Math.PI / 2, r = (i % 2 ? 6.4 : 15.5) * S; if (i) st.lineTo(Math.cos(a) * r, Math.sin(a) * r); else st.moveTo(Math.cos(a) * r, Math.sin(a) * r); }
  st.closePath();
  const sg = new THREE.ExtrudeGeometry(st, { depth: 3 * S, bevelEnabled: true, bevelThickness: 4.2 * S, bevelSize: 3.4 * S, bevelSegments: 10, curveSegments: 6 });
  sg.center(); sg.computeVertexNormals();
  const star = fur(new THREE.Mesh(sg, orDoux), 1.2 * S, 10, 4); star.position.set(0, 47 * S, 0); star.rotation.z = 0.06; ant.add(star);
}
// Corps : un gros œuf de minky ivoire qui s'assoit bien à plat
const body = new THREE.Group(); doji.add(body);
const BODY_K = 1.85;
{
  const prof = new THREE.SplineCurve(([[0, -26], [12, -26], [22.5, -23], [27.6, -14], [29.2, -2], [28.4, 10], [24.6, 20], [17, 27.6], [8.4, 31.2], [0, 32]] as [number, number][])
    .map(([r, y]) => new THREE.Vector2(r * S * BODY_K, y * S * BODY_K)));
  const g = new THREE.LatheGeometry(prof.getPoints(80), 128);
  const uv = g.attributes.uv as THREE.BufferAttribute; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * 6, uv.getY(i) * 3);
  body.add(fur(new THREE.Mesh(g, ivoire), 2.6 * S, 14, 3));
  // coutures des quatre panneaux
  for (let k = 0; k < 4; k++) {
    const a = Math.PI / 4 + (k * Math.PI) / 2; const pts = prof.getPoints(60).map((p) => new THREE.Vector3(Math.sin(a) * p.x * 0.985, p.y, Math.cos(a) * p.x * 0.985));
    body.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 80, 0.7 * S, 6, false), couture(0xd9d1c2)));
  }
  // ceinture de satin or
  const belt = new THREE.Mesh(new THREE.TorusGeometry(29.1 * S * BODY_K, 1.7 * S, 16, 160), satinOr); belt.rotation.x = Math.PI / 2; belt.position.y = -3.5 * S * BODY_K; belt.scale.set(1, 1, 1.15); body.add(belt);
  // cœur brodé dans l'anneau du « réacteur »
  const zc = 28.7 * S * BODY_K;
  const ring = new THREE.Mesh(new THREE.TorusGeometry(7.2 * S, 1.5 * S, 14, 48), brodOr); ring.position.set(0, 10 * S * BODY_K, zc); ring.scale.set(1, 1, 0.5); ring.rotation.x = -0.32; body.add(ring);
  const hs = new THREE.Shape(); hs.moveTo(0, -3.4 * S); hs.bezierCurveTo(-5.6 * S, 0.6 * S, -2.6 * S, 4.8 * S, 0, 2.2 * S); hs.bezierCurveTo(2.6 * S, 4.8 * S, 5.6 * S, 0.6 * S, 0, -3.4 * S);
  const hg = new THREE.ExtrudeGeometry(hs, { depth: 0.6 * S, bevelEnabled: true, bevelThickness: 0.9 * S, bevelSize: 0.7 * S, bevelSegments: 5 }); hg.center();
  const heart = new THREE.Mesh(hg, brodOr); heart.position.set(0, 10 * S * BODY_K, zc + 0.6 * S); heart.rotation.x = -0.32; body.add(heart);
  // pieds ronds, semelles dorées
  for (const side of [-1, 1]) {
    const foot = fur(new THREE.Mesh(new THREE.SphereGeometry(13 * S, 40, 24), ivoire), 2 * S, 10, 2); foot.scale.set(1, 0.6, 1.3); foot.position.set(side * 21 * S, -44 * S, 30 * S); body.add(foot);
    const sole = new THREE.Mesh(new THREE.CylinderGeometry(8.5 * S, 8.5 * S, 0.8 * S, 40), orDoux); sole.scale.set(1, 1, 1.3); sole.position.set(side * 21 * S, -48 * S, 36.5 * S); sole.rotation.x = -1.2; body.add(sole);
  }
  // étiquette cousue sur le flanc : ruban de satin crème, « MACROARSENAL » brodé or
  const tagTex = canvasTex(512, 160, (g) => {
    g.fillStyle = '#f4ecdc'; g.fillRect(0, 0, 512, 160);
    g.strokeStyle = '#d1a954'; g.lineWidth = 3; g.setLineDash([9, 6]); g.strokeRect(12, 12, 488, 136);
    g.fillStyle = '#9a7426'; g.font = '600 58px "Bodoni Moda", Georgia, serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
    (g as unknown as { letterSpacing: string }).letterSpacing = '6px'; g.fillText('MACROARSENAL', 256, 74);
    g.font = '500 20px "JetBrains Mono", monospace'; (g as unknown as { letterSpacing: string }).letterSpacing = '5px'; g.fillText('GLOBAL MACRO TERMINAL', 256, 122);
  }, false);
  const tagMat = new THREE.MeshPhysicalMaterial({ map: tagTex, roughness: 0.4, sheen: 0.5, sheenColor: new THREE.Color(0xffffff), side: THREE.DoubleSide });
  const tg = new THREE.PlaneGeometry(19 * S, 6 * S, 20, 4); const tp = tg.attributes.position;
  for (let i = 0; i < tp.count; i++) tp.setZ(i, Math.sin((tp.getX(i) / (19 * S) + 0.5) * Math.PI) * 1.2 * S);
  tg.computeVertexNormals();
  const tag = new THREE.Mesh(tg, tagMat); const ta = -0.95;
  tag.position.set(Math.sin(ta) * 29.9 * S * BODY_K, -17 * S * BODY_K, Math.cos(ta) * 29.9 * S * BODY_K); tag.rotation.set(0.08, ta, -0.1); body.add(tag);
}
// Bras courts et ronds, ouverts pour un câlin
for (const side of [-1, 1]) {
  const sh = new THREE.Group(); sh.position.set(side * 26.5 * S * BODY_K, 12 * S * BODY_K, 4 * S); body.add(sh);
  sh.rotation.set(-0.55, side * 0.35, side * 0.85);
  const prof = [[0, -36], [8.6, -35], [12.8, -31], [13.6, -25], [12.2, -18], [11.4, -9], [10.4, -1], [8.6, 4], [0, 6]].map(([r, y]) => new THREE.Vector2(r * S, y * S));
  const arm = fur(new THREE.Mesh(new THREE.LatheGeometry(new THREE.SplineCurve(prof).getPoints(40), 48), ivoire), 2.4 * S, 12, 3); sh.add(arm);
  const cuff = new THREE.Mesh(new THREE.TorusGeometry(10.6 * S, 1.6 * S, 12, 48), satinOr); cuff.rotation.x = Math.PI / 2; cuff.position.y = -22 * S; sh.add(cuff);
}
// La tête repose sur le corps (cousue au cou)
{
  const bottom = (CY - R(-Math.PI / 2) * 0.96) * 0.88;
  head.position.y = 32 * S * BODY_K - bottom - 12 * S;
  head.rotation.z = 0.05; head.rotation.x = -0.04; head.scale.setScalar(0.88);
  body.position.y = 26 * S * BODY_K + 0.2 * S;
  head.position.y += body.position.y;
}
doji.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } });
growFur();

// --- Studio photo ----------------------------------------------------------------------------------------------------------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = FOND === 'nuit' ? 1.05 : 1.0;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.VSMShadowMap;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = FOND === 'nuit' ? 0.35 : 0.55;
scene.add(doji);
// fond continu (sol qui remonte en mur) : papier crème, ou nuit d'encre pour la version « boutique de luxe »
{
  const pts: THREE.Vector2[] = [];
  for (let i = 0; i <= 120; i++) { const u = i / 120; // sol de z = 4 à 0,  puis quart de cercle de rayon 2,  puis mur
    if (u < 0.35) pts.push(new THREE.Vector2(-4 + (u / 0.35) * 4.4, 0));
    else if (u < 0.75) { const a = ((u - 0.35) / 0.4) * Math.PI / 2; pts.push(new THREE.Vector2(0.4 + Math.sin(a) * 2, 2 - Math.cos(a) * 2)); }
    else pts.push(new THREE.Vector2(2.4, 2 + ((u - 0.75) / 0.25) * 8)); }
  const geo = new THREE.BufferGeometry(); const pos: number[] = []; const idx: number[] = []; const X = 14;
  pts.forEach((p) => { pos.push(-X, p.y, -p.x + 0.3, X, p.y, -p.x + 0.3); });
  for (let i = 0; i < pts.length - 1; i++) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setIndex(idx); geo.computeVertexNormals();
  const paper = new THREE.MeshStandardMaterial({ color: FOND === 'nuit' ? 0x101218 : 0xeee4d3, roughness: 1, side: THREE.DoubleSide });
  const cyc = new THREE.Mesh(geo, paper); cyc.receiveShadow = true; scene.add(cyc);
}
const hemi = new THREE.HemisphereLight(FOND === 'nuit' ? 0x9aa6c8 : 0xfff6ea, FOND === 'nuit' ? 0x0c0d12 : 0xcdbb9f, FOND === 'nuit' ? 0.35 : 0.75); scene.add(hemi);
const key = new THREE.DirectionalLight(0xffecd2, FOND === 'nuit' ? 2.6 : 3.1); key.position.set(-2.2, 3.4, 3.2); key.castShadow = true;
key.shadow.mapSize.set(2048, 2048); key.shadow.camera.left = -1.2; key.shadow.camera.right = 1.2; key.shadow.camera.top = 2.2; key.shadow.camera.bottom = -0.6;
key.shadow.camera.near = 0.5; key.shadow.camera.far = 9; key.shadow.radius = 14; key.shadow.blurSamples = 24; key.shadow.bias = -0.0004; scene.add(key);
const rim = new THREE.DirectionalLight(FOND === 'nuit' ? 0xd9b46a : 0xfff8ee, FOND === 'nuit' ? 2.6 : 2.4); rim.position.set(2.6, 2.2, -2.4); scene.add(rim);
const fill = new THREE.DirectionalLight(0xe8eeff, FOND === 'nuit' ? 0.25 : 0.5); fill.position.set(3, 1.2, 2.5); scene.add(fill);
if (FOND === 'nuit') { const glow = new THREE.PointLight(0xffc86a, 1.6, 3, 2); glow.position.set(0.6, 2.4, 0.6); scene.add(glow); }
// halo doux sur le fond, derrière la peluche (profondeur, comme en studio photo)
const spot = new THREE.SpotLight(FOND === 'nuit' ? 0x3a4a78 : 0xfff3df, FOND === 'nuit' ? 30 : 14, 9, 0.5, 1, 1.4); spot.position.set(0.3, 1.6, 1.6); spot.target.position.set(0, 1.1, -2.1); scene.add(spot, spot.target);

// --- Cadrages ---------------------------------------------------------------------------------------------------------------
const box = new THREE.Box3().setFromObject(doji); const ctr = box.getCenter(new THREE.Vector3()); const size = box.getSize(new THREE.Vector3());
const cam = new THREE.PerspectiveCamera(26, W / H, 0.05, 50);
const dist = (Math.max(size.y * 1.18, size.x * 1.25 * (H / W))) / (2 * Math.tan(THREE.MathUtils.degToRad(13)));
const views: Record<string, () => void> = {
  '34': () => { cam.position.set(ctr.x - dist * 0.42, ctr.y + dist * 0.16, ctr.z + dist * 0.9); cam.lookAt(ctr.x, ctr.y - size.y * 0.02, ctr.z); },
  face: () => { cam.position.set(ctr.x, ctr.y + dist * 0.08, ctr.z + dist); cam.lookAt(ctr.x, ctr.y, ctr.z); },
  dos: () => { cam.position.set(ctr.x + dist * 0.55, ctr.y + dist * 0.12, ctr.z - dist * 0.84); cam.lookAt(ctr.x, ctr.y, ctr.z); },
  detail: () => { const hc = new THREE.Box3().setFromObject(head).getCenter(new THREE.Vector3()); cam.fov = 22; cam.updateProjectionMatrix(); cam.position.set(hc.x - 1.0, hc.y + 0.32, hc.z + 3.6); cam.lookAt(hc.x, hc.y - 0.02, hc.z); },
};
(views[VUE] ?? views['34'])();
renderer.render(scene, cam);
(window as unknown as { __ready: boolean }).__ready = true;

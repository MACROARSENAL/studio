import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

/**
 * Doji en doudou (17/10/2026, Kévin : « plus en mode doudou pour les enfants », la première peluche paraissait fade).
 * Tout est rond, moelleux et chaleureux : tête-bouclier bien gonflée en minky bleu nuit, visage crème avec yeux-chandelles
 * brodés bleu nuit et une étincelle, grosses joues roses, bras qui pendent, antenne souple jaune soleil et grosse étoile,
 * petites étoiles brodées sur le ventre, étiquette de satin. Rendu photo de produit, ambiance chambre d'enfant.
 * Adresse : ?vue=34|face|detail&fond=creme|rose&w=1600&h=2000
 */
const Q = new URLSearchParams(location.search);
const VUE = Q.get('vue') ?? '34';
const FOND = Q.get('fond') ?? 'creme';
const W = Number(Q.get('w') ?? 1600), H = Number(Q.get('h') ?? 2000);
const S = 0.01;

// --- Bouclier du logo, très arrondi ----------------------------------------------------------------------------------------
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
function makeRadius(smooth: number) {
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
  const R = new Float32Array(N);
  for (let pass = 0; pass < 2; pass++) {
    const src = pass ? R.slice() : raw;
    for (let i = 0; i < N; i++) { let s = 0; for (let j = -smooth; j <= smooth; j++) s += src[(i + j + N) % N]; R[i] = s / (2 * smooth + 1); }
  }
  const at = (th: number) => { let u = ((th + Math.PI) / (Math.PI * 2)) * N; u = ((u % N) + N) % N; const i = Math.floor(u), f = u - i; return R[i] * (1 - f) + R[(i + 1) % N] * f; };
  return { cy, at };
}
function pillow(radius: (th: number) => number, cy: number, depth: number, E: number, pinch = 0.09, segU = 260, segV = 130) {
  const pos: number[] = []; const idx: number[] = [];
  for (let j = 0; j <= segV; j++) {
    const phi = (j / segV) * Math.PI; const sp = Math.sin(phi), cp = Math.cos(phi);
    const rr = Math.pow(Math.max(0, sp), E); const zz = Math.sign(cp) * Math.pow(Math.abs(cp), E) * depth;
    const k = 1 - pinch * Math.exp(-Math.pow(Math.abs(cp) / 0.1, 2));
    for (let i = 0; i <= segU; i++) { const th = (i / segU) * Math.PI * 2; const R = radius(th) * k; pos.push(Math.cos(th) * rr * R, cy + Math.sin(th) * rr * R, zz); }
  }
  for (let j = 0; j < segV; j++) for (let i = 0; i < segU; i++) { const a = j * (segU + 1) + i, b = a + segU + 1; idx.push(a, b, a + 1, b, b + 1, a + 1); }
  let g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
  g = mergeVertices(g, 1e-6); g.computeVertexNormals();
  g.computeBoundingBox(); const bb = g.boundingBox!; const p = g.attributes.position; const uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) { uv[i * 2] = (p.getX(i) - bb.min.x) / (bb.max.x - bb.min.x) * 3; uv[i * 2 + 1] = (p.getY(i) - bb.min.y) / (bb.max.y - bb.min.y) * 3.6 + (p.getZ(i) < 0 ? 5 : 0); }
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  return g;
}

// --- Textures -------------------------------------------------------------------------------------------------------------
function canvasTex(w: number, h: number, draw: (g: CanvasRenderingContext2D) => void, repeat = true) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d')!; draw(g);
  const t = new THREE.CanvasTexture(c); if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; return t;
}
let seed = 11; const rnd = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
const pile = canvasTex(1024, 1024, (g) => {
  g.fillStyle = '#808080'; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 70000; i++) { const x = rnd() * 1024, y = rnd() * 1024, l = 2 + rnd() * 6, a = 1.2 + (rnd() - 0.5) * 1.2, v = Math.floor(80 + rnd() * 130);
    g.strokeStyle = `rgba(${v},${v},${v},0.55)`; g.lineWidth = 0.8 + rnd() * 0.9; g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke(); }
});
const strands = canvasTex(512, 512, (g) => {
  g.fillStyle = '#000'; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 30000; i++) { const x = rnd() * 512, y = rnd() * 512, v = Math.floor(80 + rnd() * 175); g.fillStyle = `rgb(${v},${v},${v})`; g.beginPath(); g.arc(x, y, 0.7 + rnd() * 1.0, 0, Math.PI * 2); g.fill(); }
});
const satinBump = (angle: number) => canvasTex(256, 256, (g) => {
  g.fillStyle = '#808080'; g.fillRect(0, 0, 256, 256); g.translate(128, 128); g.rotate(angle); g.translate(-256, -256);
  for (let x = 0; x < 512; x += 5) { const v = 150 + Math.floor(rnd() * 60); g.fillStyle = `rgb(${v},${v},${v})`; g.fillRect(x, 0, 3, 512); g.fillStyle = 'rgb(70,70,70)'; g.fillRect(x + 3, 0, 1.2, 512); }
});
const thread = (base: string, dark: string, angle: number, rep: number) => {
  const t = canvasTex(256, 256, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 256); g.translate(128, 128); g.rotate(angle); g.translate(-256, -256);
    for (let x = 0; x < 512; x += 5) { g.fillStyle = dark; g.globalAlpha = 0.3 + rnd() * 0.25; g.fillRect(x + 3, 0, 1.4, 512); } });
  t.colorSpace = THREE.SRGBColorSpace; t.repeat.set(rep, rep); return t;
};

// --- Matières : tout doux --------------------------------------------------------------------------------------------------
const minky = (color: number, sheen: number, bump = 1.3) => new THREE.MeshPhysicalMaterial({
  color, roughness: 0.97, metalness: 0, specularIntensity: 0.15, sheen: 1, sheenRoughness: 0.32, sheenColor: new THREE.Color(sheen), bumpMap: pile, bumpScale: bump,
});
const bleuNuit = minky(0x233166, 0xaebcf2);   // la tête : bleu nuit chaleureux (le noir Arsenal, en version enfant)
const creme = minky(0xf5e6cc, 0xfff8ec);       // visage et ventre : crème
const soleil = minky(0xf2b93b, 0xffeab0);      // étoile, oreilles, pattes : jaune soleil (l'or du logo, en joyeux)
const satinOr = new THREE.MeshPhysicalMaterial({ color: 0xe9c06a, roughness: 0.33, metalness: 0.08, sheen: 0.8, sheenColor: new THREE.Color(0xfff3cf), sheenRoughness: 0.28, bumpMap: satinBump(0.6), bumpScale: 1.4 });
const brodBleu = new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: thread('#26335f', '#0d1430', 0, 1), roughness: 0.5, sheen: 0.7, sheenColor: new THREE.Color(0x8fa2e6), bumpMap: satinBump(0), bumpScale: 3 });
const brodBlanc = new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.45, sheen: 0.6, sheenColor: new THREE.Color(0xffffff) });
const brodOr = new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: thread('#efc35c', '#9a7426', 0.6, 2), roughness: 0.42, sheen: 0.6, sheenColor: new THREE.Color(0xfff2c8), bumpMap: satinBump(0.6), bumpScale: 2.5 });
const joue = new THREE.MeshPhysicalMaterial({ color: 0xf59aa2, roughness: 1, sheen: 0.8, sheenColor: new THREE.Color(0xffd8dc), bumpMap: pile, bumpScale: 0.6 });
const couture = (color: number) => new THREE.MeshStandardMaterial({ color, roughness: 1 });

// --- Poils ------------------------------------------------------------------------------------------------------------------
const furTargets: { mesh: THREE.Mesh; len: number; layers: number; rep: number }[] = [];
const fur = (mesh: THREE.Mesh, len = 3 * S, layers = 16, rep = 6) => { furTargets.push({ mesh, len, layers, rep }); return mesh; };
function growFur() {
  for (const { mesh, len, layers, rep } of furTargets) {
    const base = mesh.material as THREE.MeshPhysicalMaterial;
    for (let k = 1; k <= layers; k++) {
      const u = k / layers; const m = base.clone();
      m.alphaMap = strands.clone(); m.alphaMap.repeat.set(rep, rep); m.alphaMap.needsUpdate = true;
      m.alphaTest = 0.16 + 0.74 * u; m.bumpMap = null;
      m.color = base.color.clone().multiplyScalar(0.7 + 0.3 * Math.pow(u, 0.6)).lerp(new THREE.Color(0xffffff), 0.06 * u);
      const off = len * u;
      m.onBeforeCompile = (sh) => { sh.vertexShader = sh.vertexShader.replace('#include <begin_vertex>', `#include <begin_vertex>\n transformed += normalize(objectNormal) * ${off.toFixed(5)};`); };
      m.customProgramCacheKey = () => `fur${off.toFixed(5)}${k}`;
      const shell = new THREE.Mesh(mesh.geometry, m); shell.castShadow = false; shell.receiveShadow = true; mesh.add(shell);
    }
  }
}

// --- Le doudou --------------------------------------------------------------------------------------------------------------
const doji = new THREE.Group();
const { cy: CY, at: R } = makeRadius(48);
const DEPTH = 26 * S, E = 0.95;
const zFront = (s: number) => DEPTH * Math.pow(Math.max(0, 1 - Math.pow(Math.min(1, s), 2 / E)), E / 2);
const zFace = (x: number, y: number) => { const th = Math.atan2(y - CY, x); return zFront(Math.hypot(x, y - CY) / R(th)); };

const head = new THREE.Group(); doji.add(head);
head.add(fur(new THREE.Mesh(pillow(R, CY, DEPTH, E), bleuNuit), 3.4 * S, 16, 22));
{ // couture du pourtour
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i < 400; i++) { const th = (i / 400) * Math.PI * 2; const r = R(th) * 0.905; pts.push(new THREE.Vector3(Math.cos(th) * r, CY + Math.sin(th) * r, 0)); }
  head.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true), 600, 1.3 * S, 8, true), couture(0x1c2650)));
}
// Visage crème, un peu bombé, cerclé d'un cordon or
const SV = 0.78, LIFT = 1.2 * S;
{
  const rings = 56, segs = 260; const pos: number[] = [0, CY, zFront(0) + LIFT + 2.4 * S]; const idx: number[] = [];
  for (let k = 1; k <= rings; k++) { const s = SV * (k / rings); for (let i = 0; i < segs; i++) { const th = (i / segs) * Math.PI * 2; const r = s * R(th); const u = k / rings; pos.push(Math.cos(th) * r, CY + Math.sin(th) * r, zFront(s) + LIFT + 2.4 * S * (1 - u * u)); } }
  for (let i = 0; i < segs; i++) idx.push(0, 1 + i, 1 + ((i + 1) % segs));
  for (let k = 1; k < rings; k++) { const a0 = 1 + (k - 1) * segs, b0 = 1 + k * segs; for (let i = 0; i < segs; i++) { const i1 = (i + 1) % segs; idx.push(a0 + i, b0 + i, a0 + i1, b0 + i, b0 + i1, a0 + i1); } }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
  const uv: number[] = []; for (let i = 0; i < pos.length; i += 3) uv.push(pos[i] * 3, pos[i + 1] * 3); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals(); head.add(fur(new THREE.Mesh(g, creme), 1.6 * S, 10, 10));
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i < 360; i++) { const th = (i / 360) * Math.PI * 2; const r = SV * R(th); pts.push(new THREE.Vector3(Math.cos(th) * r, CY + Math.sin(th) * r, zFront(SV) + LIFT * 0.6)); }
  head.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true), 520, 2.4 * S, 18, true), satinOr));
}
const FACE = (x: number, y: number, extra = 0) => { const s = Math.hypot(x * S, y * S - CY) / R(Math.atan2(y * S - CY, x * S)) / SV; return zFace(x * S, y * S) + LIFT + 2.4 * S * (1 - Math.min(1, s) ** 2) + extra; };
// Yeux-chandelles brodés bleu nuit, bien ronds, avec une étincelle
const EYE_X = 21.5, EYE_Y = -9;
for (const side of [-1, 1]) {
  const x = side * EYE_X;
  const eye = new THREE.Mesh(new RoundedBoxGeometry(17 * S, 28 * S, 3 * S, 6, 8 * S), brodBleu);
  eye.position.set(x * S, EYE_Y * S, FACE(x, EYE_Y, 0.6 * S)); eye.rotation.y = side * -0.12; head.add(eye);
  for (const dy of [1, -1]) {
    const wick = new THREE.Mesh(new THREE.CapsuleGeometry(1.3 * S, 4 * S, 6, 12), brodBleu);
    const yy = EYE_Y + dy * 18.6; wick.position.set(x * S, yy * S, FACE(x, yy, 0.5 * S)); head.add(wick);
  }
  const spark = new THREE.Mesh(new THREE.SphereGeometry(3.3 * S, 20, 14), brodBlanc); spark.scale.set(1, 1, 0.45);
  spark.position.set((x - 2.6 * side) * S, (EYE_Y + 6) * S, FACE(x, EYE_Y, 2.1 * S)); head.add(spark);
  const spark2 = new THREE.Mesh(new THREE.SphereGeometry(1.2 * S, 16, 10), brodBlanc); spark2.scale.set(1, 1, 0.45);
  spark2.position.set((x + 2.8 * side) * S, (EYE_Y - 5) * S, FACE(x, EYE_Y, 2.1 * S)); head.add(spark2);
  const cheek = new THREE.Mesh(new THREE.SphereGeometry(8.5 * S, 32, 20), joue); cheek.scale.set(1.2, 0.85, 0.2);
  const bx = side * 33, by = -29; cheek.position.set(bx * S, by * S, FACE(bx, by, 0.4 * S)); cheek.rotation.y = side * 0.3; head.add(cheek);
}
{ // grand sourire brodé
  const MY = -33;
  const smile = new THREE.Mesh(new THREE.TorusGeometry(6.4 * S, 1.7 * S, 14, 48, Math.PI * 0.9), brodBleu);
  smile.rotation.z = Math.PI * 1.05; smile.scale.set(1, 1, 0.5); smile.position.set(0, MY * S, FACE(0, MY, 0.6 * S)); head.add(smile);
}
// Oreilles : pompons jaune soleil
const HALF_W = R(0);
for (const side of [-1, 1]) {
  const ear = fur(new THREE.Mesh(new THREE.SphereGeometry(12 * S, 40, 26), soleil), 2.6 * S, 12, 3); ear.scale.set(0.62, 1, 1);
  ear.position.set(side * (HALF_W * 0.93 + 3 * S), 14 * S, 0); head.add(ear);
}
// Antenne souple (légèrement courbée) et grosse étoile toute douce
{
  const topY = CY + R(Math.PI / 2) * 0.9;
  const base = new THREE.Vector3(L2(138, 0).x * 0.9, topY - 3 * S, 0);
  const curve = new THREE.CatmullRomCurve3([base, base.clone().add(new THREE.Vector3(0.5 * S, 12 * S, 0)), base.clone().add(new THREE.Vector3(4 * S, 24 * S, 0)), base.clone().add(new THREE.Vector3(10 * S, 33 * S, 0))]);
  head.add(fur(new THREE.Mesh(new THREE.TubeGeometry(curve, 60, 5 * S, 24, false), soleil), 2 * S, 12, 3));
  const cap = new THREE.Mesh(new THREE.SphereGeometry(5 * S, 24, 16), soleil); cap.position.copy(base); head.add(cap);
  const st = new THREE.Shape();
  for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2 - Math.PI / 2, r = (i % 2 ? 8.5 : 20) * S; if (i) st.lineTo(Math.cos(a) * r, Math.sin(a) * r); else st.moveTo(Math.cos(a) * r, Math.sin(a) * r); }
  st.closePath();
  const sg = new THREE.ExtrudeGeometry(st, { depth: 4 * S, bevelEnabled: true, bevelThickness: 6 * S, bevelSize: 5.2 * S, bevelSegments: 12, curveSegments: 6 });
  sg.center(); sg.computeVertexNormals();
  const star = fur(new THREE.Mesh(sg, soleil), 2.2 * S, 12, 3); const tip = curve.getPoint(1);
  star.position.set(tip.x + 9 * S, tip.y + 17 * S, 0); star.rotation.z = -0.22; head.add(star);
}
// Corps : petit, rond, crème, semé d'étoiles brodées
const body = new THREE.Group(); doji.add(body);
const BK = 1.22;
const prof = new THREE.SplineCurve(([[0, -29], [12, -28.5], [21.5, -24], [26, -13], [26.4, 0], [24, 12], [19, 22], [11, 29], [0, 31.5]] as [number, number][])
  .map(([r, y]) => new THREE.Vector2(r * S * BK, y * S * BK)));
{
  const g = new THREE.LatheGeometry(prof.getPoints(80), 128);
  const uv = g.attributes.uv as THREE.BufferAttribute; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * 6, uv.getY(i) * 3);
  body.add(fur(new THREE.Mesh(g, creme), 3 * S, 16, 3));
  for (let k = 0; k < 4; k++) {
    const a = Math.PI / 4 + (k * Math.PI) / 2; const pts = prof.getPoints(60).map((p) => new THREE.Vector3(Math.sin(a) * p.x * 0.99, p.y, Math.cos(a) * p.x * 0.99));
    body.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 80, 0.8 * S, 6, false), couture(0xe6d8c2)));
  }
  // petites étoiles brodées or, posées sur le ventre
  const star = new THREE.Shape();
  for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2 - Math.PI / 2, r = (i % 2 ? 1.5 : 4) * S; if (i) star.lineTo(Math.cos(a) * r, Math.sin(a) * r); else star.moveTo(Math.cos(a) * r, Math.sin(a) * r); }
  star.closePath();
  const sg = new THREE.ExtrudeGeometry(star, { depth: 0.4 * S, bevelEnabled: true, bevelThickness: 0.6 * S, bevelSize: 0.5 * S, bevelSegments: 3 }); sg.center();
  const spots: [number, number][] = [[-0.62, 12], [0.45, 18], [0.05, 4], [-0.35, -8], [0.7, -4], [-0.9, -2], [0.95, 8], [0.3, -16], [-0.6, -18], [1.25, -12], [-1.3, 8]];
  for (const [a, y] of spots) {
    const yy = y * S * BK; const pr = prof.getPoints(200).reduce((b, p) => (Math.abs(p.y - yy) < Math.abs(b.y - yy) ? p : b));
    const m = new THREE.Mesh(sg, brodOr); m.position.set(Math.sin(a) * (pr.x + 3.2 * S), yy, Math.cos(a) * (pr.x + 3.2 * S));
    m.lookAt(m.position.clone().multiplyScalar(2).setY(yy)); m.rotateZ(a * 0.7); body.add(m);
  }
  // pieds ronds aux semelles jaune soleil
  for (const side of [-1, 1]) {
    const foot = fur(new THREE.Mesh(new THREE.SphereGeometry(10 * S, 40, 24), creme), 2.4 * S, 12, 2); foot.scale.set(1, 0.62, 1.3); foot.position.set(side * 13 * S, -34 * S, 19 * S); body.add(foot);
    const sole = fur(new THREE.Mesh(new THREE.SphereGeometry(6.8 * S, 32, 16), soleil), 1.6 * S, 10, 2); sole.scale.set(1, 1.2, 0.3); sole.position.set(side * 13 * S, -35.6 * S, 31.2 * S); sole.rotation.x = -0.35; body.add(sole);
  }
  // étiquette de satin (boucle de ruban cousue dans la couture)
  const tagTex = canvasTex(512, 160, (g) => {
    g.fillStyle = '#fbf3e2'; g.fillRect(0, 0, 512, 160);
    g.strokeStyle = '#e9c06a'; g.lineWidth = 4; g.setLineDash([10, 7]); g.strokeRect(12, 12, 488, 136);
    g.fillStyle = '#2c3a6e'; g.font = '600 56px "Bodoni Moda", Georgia, serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
    (g as unknown as { letterSpacing: string }).letterSpacing = '6px'; g.fillText('MACROARSENAL', 256, 72);
    g.fillStyle = '#c99a3a'; g.font = '500 22px "JetBrains Mono", monospace'; (g as unknown as { letterSpacing: string }).letterSpacing = '6px'; g.fillText('DOJI ★ DOUDOU', 256, 122);
  }, false);
  tagTex.colorSpace = THREE.SRGBColorSpace;
  const tagMat = new THREE.MeshPhysicalMaterial({ map: tagTex, roughness: 0.35, sheen: 0.6, sheenColor: new THREE.Color(0xffffff), side: THREE.DoubleSide });
  const tg = new THREE.PlaneGeometry(18 * S, 5.6 * S, 24, 4); const tp = tg.attributes.position;
  for (let i = 0; i < tp.count; i++) tp.setZ(i, Math.sin((tp.getX(i) / (18 * S) + 0.5) * Math.PI) * 1.6 * S);
  tg.computeVertexNormals();
  const tag = new THREE.Mesh(tg, tagMat); const ta = -0.95; const pr = prof.getPoints(200).reduce((b, p) => (Math.abs(p.y + 12 * S * BK) < Math.abs(b.y + 12 * S * BK) ? p : b));
  tag.position.set(Math.sin(ta) * (pr.x + 2.6 * S), -12 * S * BK, Math.cos(ta) * (pr.x + 2.6 * S)); tag.rotation.set(0.05, ta, -0.18); body.add(tag);
}
// Bras qui pendent, tout mous, pattes jaune soleil
for (const side of [-1, 1]) {
  const sx = side * 25 * S * BK, sy = 12 * S * BK;
  const path = new THREE.CatmullRomCurve3([new THREE.Vector3(sx * 0.86, sy, 2 * S), new THREE.Vector3(sx * 1.16, sy - 8 * S, 8 * S), new THREE.Vector3(sx * 1.26, sy - 21 * S, 15 * S), new THREE.Vector3(sx * 1.2, sy - 31 * S, 21 * S)]);
  const tube = new THREE.TubeGeometry(path, 60, 6.8 * S, 28, false);
  body.add(fur(new THREE.Mesh(tube, bleuNuit), 2.6 * S, 14, 3));
  const sh = new THREE.Mesh(new THREE.SphereGeometry(6.8 * S, 28, 18), bleuNuit); sh.position.copy(path.getPoint(0)); body.add(sh);
  const paw = fur(new THREE.Mesh(new THREE.SphereGeometry(8.2 * S, 32, 20), soleil), 2.4 * S, 12, 2); paw.scale.set(1, 1.08, 0.95); paw.position.copy(path.getPoint(1)); body.add(paw);
}
// La tête posée sur le corps, légèrement penchée (l'air tendre)
{
  const bottom = CY - R(-Math.PI / 2);
  body.position.y = 27 * S * BK + 2 * S;
  head.position.y = body.position.y + 31 * S * BK - bottom * 0.98 - 14 * S;
  head.rotation.z = 0.13; head.rotation.x = -0.07; head.rotation.y = 0.06; body.rotation.z = -0.03;
}
doji.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } });
growFur();

// --- Studio : chambre d'enfant, lumière douce ----------------------------------------------------------------------------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.92;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.VSMShadowMap;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.36;
scene.add(doji);
{
  const pts: THREE.Vector2[] = [];
  for (let i = 0; i <= 120; i++) { const u = i / 120;
    if (u < 0.35) pts.push(new THREE.Vector2(-4 + (u / 0.35) * 4.4, 0));
    else if (u < 0.75) { const a = ((u - 0.35) / 0.4) * Math.PI / 2; pts.push(new THREE.Vector2(0.4 + Math.sin(a) * 2, 2 - Math.cos(a) * 2)); }
    else pts.push(new THREE.Vector2(2.4, 2 + ((u - 0.75) / 0.25) * 8)); }
  const geo = new THREE.BufferGeometry(); const pos: number[] = []; const idx: number[] = []; const X = 14;
  pts.forEach((p) => { pos.push(-X, p.y, -p.x + 0.3, X, p.y, -p.x + 0.3); });
  for (let i = 0; i < pts.length - 1; i++) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setIndex(idx); geo.computeVertexNormals();
  const paper = new THREE.MeshStandardMaterial({ color: FOND === 'rose' ? 0xf4d9d4 : 0xf3e2cf, roughness: 1, side: THREE.DoubleSide });
  const cyc = new THREE.Mesh(geo, paper); cyc.receiveShadow = true; scene.add(cyc);
}
scene.add(new THREE.HemisphereLight(0xfff7ee, 0xe2c9ad, 0.38));
const key = new THREE.DirectionalLight(0xffeedb, 2.5); key.position.set(-2.2, 3.4, 3.2); key.castShadow = true;
key.shadow.mapSize.set(2048, 2048); key.shadow.camera.left = -1.3; key.shadow.camera.right = 1.3; key.shadow.camera.top = 2.4; key.shadow.camera.bottom = -0.6;
key.shadow.camera.near = 0.5; key.shadow.camera.far = 9; key.shadow.radius = 24; key.shadow.blurSamples = 24; key.shadow.bias = -0.0004; scene.add(key);
const rim = new THREE.DirectionalLight(0xffd9a0, 3.4); rim.position.set(2.6, 2.4, -2.4); scene.add(rim);
const rim2 = new THREE.DirectionalLight(0xbfd2ff, 1.6); rim2.position.set(-2.8, 1.6, -2.0); scene.add(rim2);
const fill = new THREE.DirectionalLight(0xfff2ec, 0.7); fill.position.set(3, 1.2, 2.5); scene.add(fill);
const spot = new THREE.SpotLight(0xffeedd, 26, 9, 0.5, 1, 1.4); spot.position.set(0.3, 1.7, 1.6); spot.target.position.set(0, 1.1, -2.1); scene.add(spot, spot.target);

// --- Cadrages ---------------------------------------------------------------------------------------------------------------
const box = new THREE.Box3().setFromObject(doji); const ctr = box.getCenter(new THREE.Vector3()); const size = box.getSize(new THREE.Vector3());
const cam = new THREE.PerspectiveCamera(26, W / H, 0.05, 50);
const dist = (Math.max(size.y * 1.16, size.x * 1.3 * (H / W))) / (2 * Math.tan(THREE.MathUtils.degToRad(13)));
const views: Record<string, () => void> = {
  '34': () => { cam.position.set(ctr.x - dist * 0.36, ctr.y + dist * 0.05, ctr.z + dist * 0.93); cam.lookAt(ctr.x, ctr.y - size.y * 0.03, ctr.z); },
  face: () => { cam.position.set(ctr.x, ctr.y + dist * 0.08, ctr.z + dist); cam.lookAt(ctr.x, ctr.y, ctr.z); },
  detail: () => { const hc = new THREE.Box3().setFromObject(head).getCenter(new THREE.Vector3()); cam.fov = 22; cam.updateProjectionMatrix(); cam.position.set(hc.x - 1.05, hc.y + 0.25, hc.z + 4.1); cam.lookAt(hc.x, hc.y - 0.08, hc.z); },
};
(views[VUE] ?? views['34'])();
renderer.render(scene, cam);
(window as unknown as { __ready: boolean }).__ready = true;

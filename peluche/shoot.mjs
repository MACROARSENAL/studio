import { chromium } from 'playwright';
const [dir, ...shots] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
for (const s of shots) {
  const [name, q] = s.split('|');
  const u = new URLSearchParams(q); const w = Number(u.get('w') || 1600), h = Number(u.get('h') || 2000);
  const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  p.on('pageerror', (e) => console.log('ERREUR', e.message)); p.on('console', (m) => { if (m.type() === 'error') console.log('console', m.text()); });
  await p.goto(`http://localhost:8124/peluche/${process.env.PAGE || "index"}.html?${q}`);
  await p.waitForFunction(() => window.__ready === true, null, { timeout: 600000 });
  await p.screenshot({ path: `${dir}/${name}.png` }); await p.close(); console.log('ok', name);
}
await b.close();

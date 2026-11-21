// The live LESH? mark for the site. One solid question mark: the front reads ?, the back reads the Arabic mark.
// Same geometry as brand/src/mark3d/mark.html. Drag to spin, tap to flip. Built with: npx esbuild mark.src.js --bundle --minify --format=iife --outfile=../site_src/mark.js
import { WebGLRenderer, Scene, OrthographicCamera, Group, Mesh, Shape, ExtrudeGeometry, ShapeGeometry, MeshBasicMaterial, ShaderMaterial,
  BufferAttribute, Color, Vector3, LinearSRGBColorSpace, BackSide, DoubleSide } from "three";

const P = { R: 1, w: 0.8, a0: 180, a1: -66, stem: 0.16, gap: 0.2, rd: 0.47, depth: 0.6, bevel: 0.045, bevSeg: 5, rx: 0.26, home: -0.5, outline: 0.04,
  face: "#FFFFFF", s1: "#3A4658", s2: "#1B212B", s3: "#0B0E13", line: "#0B0E13", L: [-0.55, 0.9, 0.65], t1: 0.55, t2: 0.05 };
const raw = (h) => new Color().setStyle(h, LinearSRGBColorSpace);

function qShape(e = 0) {
  const d2r = Math.PI / 180, R = P.R, h = P.w / 2 + e, N = 120, L = [], Rr = [];
  const push = (x, y, nx, ny) => { L.push([x + nx * h, y + ny * h]); Rr.push([x - nx * h, y - ny * h]); };
  const a0 = P.a0 * d2r + e / R, a1 = P.a1 * d2r;
  for (let i = 0; i <= N; i++) { const th = a0 + (a1 - a0) * i / N; push(R * Math.cos(th), R * Math.sin(th), Math.cos(th), Math.sin(th)); }
  const px = R * Math.cos(a1), py = R * Math.sin(a1), r2 = px / (1 - Math.cos(a1)), cx = px + r2 * Math.cos(a1), cy = py + r2 * Math.sin(a1);
  const f0 = a1 - Math.PI / 2, f1 = -Math.PI / 2, M = 44;
  for (let i = 1; i <= M; i++) { const f = f0 + (f1 - f0) * i / M, nx = -Math.sin(f), ny = Math.cos(f); push(cx - r2 * nx, cy - r2 * ny, nx, ny); }
  push(0, cy - P.stem - e, 1, 0);
  const s = new Shape(), pts = L.concat(Rr.reverse());
  s.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) s.lineTo(pts[i][0], pts[i][1]); s.closePath();
  return { s, dotY: cy - P.stem - P.gap - P.rd, top: R + P.w / 2, bot: cy - P.stem - P.gap - 2 * P.rd };
}
function smooth(g, deg) { // crease angle smoothing on the side walls only, the lids stay flat
  const p = g.attributes.position, n = g.attributes.normal, c = Math.cos(deg * Math.PI / 180), map = new Map(), out = n.array.slice();
  const gr = g.groups.find((x) => x.materialIndex === 1); if (!gr) return g;
  for (let i = gr.start; i < gr.start + gr.count; i++) { const k = Math.round(p.getX(i) * 2e4) + "," + Math.round(p.getY(i) * 2e4) + "," + Math.round(p.getZ(i) * 2e4); (map.get(k) || map.set(k, []).get(k)).push(i); }
  for (const ids of map.values()) for (const i of ids) { let x = 0, y = 0, z = 0; const ax = n.getX(i), ay = n.getY(i), az = n.getZ(i);
    for (const j of ids) { const bx = n.getX(j), by = n.getY(j), bz = n.getZ(j); if (ax * bx + ay * by + az * bz > c) { x += bx; y += by; z += bz; } }
    const l = Math.hypot(x, y, z) || 1; out[i * 3] = x / l; out[i * 3 + 1] = y / l; out[i * 3 + 2] = z / l; }
  g.setAttribute("normal", new BufferAttribute(out, 3)); return g;
}

export function mount(host, opts = {}) {
  const calm = !!opts.calm;
  let r;
  try { r = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" }); } catch (e) { return null; }
  const cv = r.domElement; cv.className = "mark-canvas"; cv.setAttribute("role", "img"); cv.setAttribute("aria-label", "The LESH question mark. Drag to spin it.");
  r.setClearColor(0x000000, 0);
  const sc = new Scene(), V = 2.75, cam = new OrthographicCamera(-V, V, V, -V, 0.1, 100); cam.position.set(0, 0, 20);
  const Q = qShape(), ext = { depth: P.depth, bevelEnabled: true, bevelThickness: P.bevel, bevelSize: P.bevel, bevelOffset: -P.bevel, bevelSegments: P.bevSeg, steps: 1 };
  const faceM = new MeshBasicMaterial({ color: new Color(P.face) });
  const sideM = new ShaderMaterial({ uniforms: { cA: { value: raw(P.s1) }, cB: { value: raw(P.s2) }, cC: { value: raw(P.s3) }, L: { value: new Vector3(...P.L).normalize() }, t1: { value: P.t1 }, t2: { value: P.t2 } },
    vertexShader: "varying vec3 vN; void main(){ vN = normalize(mat3(modelMatrix) * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: "uniform vec3 cA; uniform vec3 cB; uniform vec3 cC; uniform vec3 L; uniform float t1; uniform float t2; varying vec3 vN; void main(){ float d = dot(normalize(vN), L); vec3 c = d > t1 ? cA : (d > t2 ? cB : cC); gl_FragColor = vec4(c, 1.0); }" });
  const G = new Group(), solid = (sh) => smooth(new ExtrudeGeometry(sh, ext).translate(0, 0, -P.depth / 2), 40);
  const dotS = new Shape(); dotS.absarc(0, Q.dotY, P.rd, 0, Math.PI * 2, false);
  G.add(new Mesh(solid(Q.s), [faceM, sideM]), new Mesh(solid(dotS), [faceM, sideM]));
  // plugs behind both lids, so no seam can ever show what is behind the face
  const e = -(P.bevel + 0.012), zf = P.depth / 2 + P.bevel - 0.004, pm = new MeshBasicMaterial({ color: new Color(P.face), side: DoubleSide });
  const ps = new Shape(); ps.absarc(0, Q.dotY, P.rd + e, 0, Math.PI * 2, false);
  for (const z of [zf, -zf]) { const a = new Mesh(new ShapeGeometry(qShape(e).s, 24), pm), b = new Mesh(new ShapeGeometry(ps, 48), pm); a.position.z = b.position.z = z; G.add(a, b); }
  // outline hull. The lid that faces the viewer is hidden (its sliver triangles can print hairlines), so the two lids swap as the mark turns.
  const o = P.outline, e2 = Object.assign({}, ext, { depth: P.depth + 2 * o }), mk = () => new MeshBasicMaterial({ color: new Color(P.line), side: BackSide });
  const lidBack = mk(), lidFront = mk(), wall = mk();
  const hull = (sh) => { const g = new ExtrudeGeometry(sh, e2).translate(0, 0, -P.depth / 2 - o), lid = g.groups[0], side = g.groups[1], half = lid.count / 2;
    g.clearGroups(); g.addGroup(lid.start, half, 0); g.addGroup(lid.start + half, half, 1); g.addGroup(side.start, side.count, 2); return new Mesh(g, [lidBack, lidFront, wall]); };
  const dh = new Shape(); dh.absarc(0, Q.dotY, P.rd + o, 0, Math.PI * 2, false);
  G.add(hull(qShape(o).s), hull(dh));
  const mid = (Q.top + Q.bot) / 2; G.children.forEach((c) => { c.position.y = -mid; });
  const W = new Group(), piv = new Group(); W.rotation.x = P.rx; piv.add(G); W.add(piv); sc.add(W);
  host.appendChild(cv);

  // motion: a spring pulls the angle to the nearest rest pose (front or back)
  const TAU = Math.PI * 2, rest = (a) => P.home + Math.round((a - P.home) / Math.PI) * Math.PI;
  let ang = calm ? P.home : P.home - 2.6, vel = 0, target = P.home, drag = null, moved = 0, side = "", raf = 0, seen = true, t0 = performance.now(), last = t0, drop = calm ? 1 : 0;
  function size() { const s = host.clientWidth || 300, d = Math.min(window.devicePixelRatio || 1, 2); r.setPixelRatio(d); r.setSize(s, s, false); cv.style.width = cv.style.height = "100%"; }
  function frame(now) {
    raf = 0; const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (!drag) { const k = 70, c = 11; vel += (-k * (ang - target) - c * vel) * dt; ang += vel * dt; }
    if (drop < 1) drop = Math.min(1, drop + dt * 1.6);
    const t = (now - t0) / 1000, idle = calm || drag ? 0 : 1, ease = 1 - Math.pow(1 - drop, 3);
    piv.rotation.y = ang + idle * Math.sin(t * 0.9) * 0.06;
    W.position.y = (1 - ease) * 1.2 + idle * Math.sin(t * 1.3) * 0.045; W.scale.setScalar(0.82 + 0.18 * ease);
    const front = Math.cos(piv.rotation.y) > 0; lidFront.visible = !front; lidBack.visible = front;
    const s = Math.cos(ang - P.home) > 0 ? "front" : "back";
    if (s !== side && (drag || Math.abs(ang - target) < 0.9)) { side = s; host.dataset.side = s; if (opts.onside) opts.onside(s); }
    r.render(sc, cam);
    const settled = !drag && drop >= 1 && Math.abs(ang - target) < 0.002 && Math.abs(vel) < 0.002;
    if (seen && !document.hidden && !(calm && settled)) raf = requestAnimationFrame(frame);
  }
  const kick = () => { if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); } };
  cv.addEventListener("pointerdown", (ev) => { drag = { x: ev.clientX, a: ang, t: performance.now() }; moved = 0; vel = 0; try { cv.setPointerCapture(ev.pointerId); } catch (e) {} host.classList.add("held"); kick(); });
  cv.addEventListener("pointermove", (ev) => { if (!drag) return; const dx = ev.clientX - drag.x; moved = Math.max(moved, Math.abs(dx)); const na = drag.a + dx * (TAU / (host.clientWidth * 1.6)); vel = (na - ang) / 0.016 * 0.25; ang = na; });
  const up = () => { if (!drag) return; const tap = moved < 6 && performance.now() - drag.t < 500; drag = null; host.classList.remove("held");
    target = tap ? rest(ang) + Math.PI : rest(ang + vel * 0.18); if (tap) vel = 9; if (opts.onuse) opts.onuse(); kick(); };
  cv.addEventListener("pointerup", up); cv.addEventListener("pointercancel", up);
  cv.tabIndex = 0; cv.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " " || ev.key === "ArrowLeft" || ev.key === "ArrowRight") { ev.preventDefault(); target = rest(ang) + (ev.key === "ArrowLeft" ? -Math.PI : Math.PI); if (opts.onuse) opts.onuse(); kick(); } });
  if ("IntersectionObserver" in window) new IntersectionObserver((en) => { seen = en[0].isIntersecting; if (seen) kick(); }).observe(host);
  document.addEventListener("visibilitychange", kick); window.addEventListener("resize", () => { size(); kick(); });
  size(); kick();
  return { flip() { target = rest(ang) + Math.PI; kick(); }, el: cv };
}
if (typeof window !== "undefined") window.LeshMark = { mount };

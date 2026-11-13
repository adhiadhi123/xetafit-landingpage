"""
XETAFIT props renderer: glass, drink, shot glass, plinth, bubbles
=================================================================
Physically based renders of the supporting objects, so the page has no
illustrated glassware or icons.

    python tools/render_props.py              # everything (~1.5 min)
    python tools/render_props.py --bubbles    # only the hero bubble sprites

Requires: numpy, pillow, opencv-python(-headless)

Outputs (assets/images/)
------------------------
  glass-water.webp     tumbler with 200-250 ml of clear water   } layers of the same
  glass-drink.webp     the same tumbler with the finished drink } glass, rendered on
  glass-shine.webp     front-surface reflections only (on top)  } forest green #174D3A
  glass-mask.webp      where the liquid is visible (CSS mask for bubbles / cloud)
  glass-drink-arch.webp  the finished drink, full render, on the lifestyle arch green #1E5A45
  shot-amber.webp      shot glass of amber liquid ACV, on cream #F6EBD3
  plinth.webp          clay plinth with its ground shadow (transparent background)
  bubble-1..3.webp     hero carbonation sprites: thin bright ring, deeper-coral inner edge, specular point
  glass-fizz.webp      fine bubbles at the drink surface, registered to the glass layers
  tools/props-geometry.json   where the water surface / base sit, in % of the glass image

How the glass is rendered
-------------------------
Objects are surfaces of revolution described by 2D profiles (glass shell, liquid,
opaque parts). Every camera ray is traced through them with exact cone/disc
intersections. At each interface the Fresnel-reflected part picks up the studio
(two tall softboxes, a top light, two back rim strips). The refracted part continues
with Snell's law, total internal reflection, and Beer-Lambert absorption plus single
scattering inside the drink. Rays leaving through the back see the backdrop colour of
the section, so the render sits seamlessly on that colour. The first front-surface
reflection is written to its own layer (glass-shine), which lets the page put the
tablet, bubbles and drink tint between the water and the glass front.
"""
import json
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "images")
EPS = 1e-5


def srgb_to_lin(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def hex_lin(h):
    h = h.lstrip("#")
    return srgb_to_lin([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def save_rgba(path, rgb, a, quality=90):
    img = Image.fromarray((np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)]) * 255 + 0.5).astype(np.uint8), "RGBA")
    img.save(path, "WEBP", quality=quality, method=6, alpha_quality=100)
    print(f"  wrote {os.path.relpath(path, ROOT)}  {img.size[0]}x{img.size[1]}  {os.path.getsize(path)//1024} KB")


# ----------------------------------------------------------------------------
# scene description
# ----------------------------------------------------------------------------
class Solid:
    def __init__(self, pts, kind, ior=1.5, sigma_a=(0, 0, 0), sigma_s=0.0, scatter=(1, 1, 1), albedo=(1, 1, 1), name=""):
        self.pts, self.kind, self.ior = pts, kind, ior
        self.sigma_a = np.array(sigma_a, np.float64)
        self.sigma_s = float(sigma_s)
        self.scatter = np.array(scatter, np.float64)
        self.albedo = np.array(albedo, np.float64)
        self.name = name


def arc(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in np.linspace(a0, a1, n)]


def tumbler(r_top=1.0, r_bot=0.86, H=2.7, wall=0.05, base=0.24, level=None, liquid=None):
    """Glass shell (CCW profile) + optional liquid solid."""
    rin_top = r_top - wall
    taper = (r_top - r_bot) / H
    def r_out(y): return r_bot + taper * y
    def r_in(y): return r_out(y) - wall
    bev = 0.035
    shell = [(0.0, 0.0), (r_bot - bev, 0.0)]
    shell += arc(r_bot - bev, bev, bev, -math.pi / 2, 0.0, 5)[1:]
    shell += [(r_out(H - wall / 2), H - wall / 2)]
    shell += arc(r_top - wall / 2, H - wall / 2, wall / 2, 0.0, math.pi, 7)[1:]
    shell += [(r_in(base + 0.05), base + 0.05)]
    shell += arc(r_in(base + 0.05) - 0.05, base + 0.05, 0.05, 0.0, -math.pi / 2, 5)[1:]
    shell += [(0.0, base)]
    solids = [Solid(shell, "glass", 1.5, sigma_a=(0.035, 0.012, 0.03), name="glass")]
    if level is not None and liquid is not None:
        # liquid follows the inner wall (with the same small fillet) up to its level
        liq = [(0.0, base), ]
        liq += arc(r_in(base + 0.05) - 0.05, base + 0.05, 0.05, -math.pi / 2, 0.0, 5)
        liq += [(r_in(level), level), (0.0, level)]
        solids.append(Solid(liq, **liquid))
    return solids, dict(H=H, base=base, level=level, r_top=r_top, r_bot=r_bot, wall=wall)


def edges_of(solids):
    E = []
    for si, s in enumerate(solids):
        P = s.pts
        n = len(P)
        for i in range(n):
            (r1, y1), (r2, y2) = P[i], P[(i + 1) % n]
            if r1 < 1e-9 and r2 < 1e-9:
                continue
            dr, dy = r2 - r1, y2 - y1
            L = math.hypot(dr, dy)
            if L < 1e-12:
                continue
            E.append((si, r1, y1, r2, y2, dy / L, -dr / L))
    return E


def intersect(O, D, E):
    """t (n, len(E)) of each ray against each swept edge; inf when missed."""
    n = O.shape[0]
    T = np.full((n, len(E)), np.inf)
    ox, oy, oz = O[:, 0], O[:, 1], O[:, 2]
    dx, dy, dz = D[:, 0], D[:, 1], D[:, 2]
    for k, (_, r1, y1, r2, y2, _, _) in enumerate(E):
        if abs(y2 - y1) < 1e-9:
            ddy = np.where(np.abs(dy) < 1e-12, 1e-12, dy)
            t = (y1 - oy) / ddy
            x = ox + t * dx; z = oz + t * dz
            rr = np.sqrt(x * x + z * z)
            ok = (t > EPS) & (rr >= min(r1, r2) - 1e-9) & (rr <= max(r1, r2) + 1e-9)
            T[:, k] = np.where(ok, t, np.inf)
            continue
        B = (r2 - r1) / (y2 - y1)
        A = r1 - B * y1
        a = dx * dx + dz * dz - B * B * dy * dy
        b = 2 * (ox * dx + oz * dz - B * dy * (A + B * oy))
        c = ox * ox + oz * oz - (A + B * oy) ** 2
        disc = b * b - 4 * a * c
        sq = np.sqrt(np.maximum(disc, 0))
        small = np.abs(a) < 1e-12
        a_ = np.where(small, 1.0, a)
        t1 = np.where(small, -c / np.where(np.abs(b) < 1e-12, 1e-12, b), (-b - sq) / (2 * a_))
        t2 = np.where(small, np.inf, (-b + sq) / (2 * a_))
        ylo, yhi = min(y1, y2) - 1e-9, max(y1, y2) + 1e-9
        best = np.full(n, np.inf)
        for tc in (t1, t2):
            y = oy + tc * dy
            ok = (disc >= 0) & (tc > EPS) & (y >= ylo) & (y <= yhi) & ((A + B * y) >= -1e-9)
            best = np.where(ok & (tc < best), tc, best)
        T[:, k] = best
    return T


# ----------------------------------------------------------------------------
# studio light
# ----------------------------------------------------------------------------
def box(az, el, a0, a1, e0, e1, soft=0.08):
    return smoothstep(a0 - soft, a0 + soft, az) * (1 - smoothstep(a1 - soft, a1 + soft, az)) * \
        smoothstep(e0 - soft, e0 + soft, el) * (1 - smoothstep(e1 - soft, e1 + soft, el))


def make_env(bg_lin, dark_scene=True):
    surround = bg_lin * (0.55 if dark_scene else 0.8)
    def env(R):
        az = np.arctan2(R[:, 0], R[:, 2])            # 0 = towards the camera
        el = np.arcsin(np.clip(R[:, 1], -1, 1))
        L = np.tile(surround, (R.shape[0], 1))
        k = np.zeros(R.shape[0])
        k += 3.2 * box(az, el, -1.35, -0.85, -0.45, 0.85)    # tall softbox, camera left
        k += 2.0 * box(az, el, 0.95, 1.4, -0.35, 0.75)       # softbox, camera right
        k += 1.5 * smoothstep(1.0, 1.3, el)                   # top light
        k += 1.9 * box(np.abs(az), el, 2.05, 2.55, -0.25, 0.6)  # rim strips behind, both sides
        floor = smoothstep(-0.15, -0.45, el)
        L = L * (1 - 0.35 * floor[:, None])
        return L + k[:, None] * np.array([1.0, 0.99, 0.96])
    def transmit(Dexit):
        # backdrop behind the object; black flags at the sides darken strongly bent rays
        L = np.tile(bg_lin, (Dexit.shape[0], 1))
        side = smoothstep(0.42, 0.85, np.abs(Dexit[:, 0]))
        L = L * (1 - (0.55 if not dark_scene else 0.35) * side[:, None])
        back = Dexit[:, 2] < 0
        return np.where(back[:, None], L, env(Dexit))
    return env, transmit


# ----------------------------------------------------------------------------
# path tracer (one reflection lookup per interface + the refracted path)
# ----------------------------------------------------------------------------
def trace(solids, O, D, env, transmit, max_events=12):
    E = edges_of(solids)
    edge_solid = np.array([e[0] for e in E])
    edge_n = np.array([[e[5], e[6]] for e in E])
    n = O.shape[0]
    S = len(solids)
    col = np.zeros((n, 3)); first = np.zeros((n, 3)); thr = np.ones((n, 3))
    inside = np.zeros((n, S), bool)
    hit_any = np.zeros(n, bool); saw_liquid = np.zeros(n, bool)
    active = np.arange(n)
    O = O.copy(); D = D.copy()
    kinds = [s.kind for s in solids]
    prio = sorted(range(S), key=lambda i: {"opaque": 0, "glass": 1, "liquid": 2}[kinds[i]])

    def medium(ins):
        m = np.full(ins.shape[0], -1)
        for i in reversed(prio):
            m = np.where(ins[:, i], i, m)
        return m
    iors = np.array([s.ior for s in solids] + [1.0])

    for ev in range(max_events):
        if active.size == 0:
            break
        o, d = O[active], D[active]
        Tm = intersect(o, d, E)
        k = np.argmin(Tm, axis=1)
        t = Tm[np.arange(len(active)), k]
        miss = ~np.isfinite(t)
        # rays leaving the scene
        if miss.any():
            idx = active[miss]
            if ev == 0:
                pass  # background pixel, never touched the object
            else:
                col[idx] += thr[idx] * transmit(D[idx])
        go = ~miss
        active, o, d, t, k = active[go], o[go], d[go], t[go], k[go]
        Tm = Tm[go]
        if active.size == 0:
            break
        if ev == 0:
            hit_any[active] = True
        p = o + d * t[:, None]
        # medium travelled through: absorption + single scattering
        m_cur = medium(inside[active])
        for si, s in enumerate(solids):
            sel = m_cur == si
            if not sel.any() or s.kind == "opaque":
                continue
            ids = active[sel]
            dist = t[sel][:, None]
            sig_t = s.sigma_a + s.sigma_s
            att = np.exp(-sig_t * dist)
            if s.sigma_s > 0:
                frac = np.where(sig_t > 0, s.sigma_s / np.maximum(sig_t, 1e-9), 0) * (1 - att)
                col[ids] += thr[ids] * frac * s.scatter
            thr[ids] *= att
            if s.kind == "liquid":
                saw_liquid[ids] = True
        # interface: toggle every solid whose surface coincides (shared walls)
        tie = Tm <= (t[:, None] + 2e-5)
        new_inside = inside[active].copy()
        for si in range(S):
            cross = (tie & (edge_solid[None, :] == si)).any(axis=1)
            new_inside[cross, si] = ~new_inside[cross, si]
        m_next = medium(new_inside)
        # normal
        en = edge_n[k]
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 2] ** 2) + 1e-12
        nrm = np.stack([en[:, 0] * p[:, 0] / rho, en[:, 1], en[:, 0] * p[:, 2] / rho], 1)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        facing = np.sum(d * nrm, axis=1) > 0
        nrm[facing] *= -1
        cosi = -np.sum(d * nrm, axis=1)
        # opaque hit: shade and stop
        opq = np.array([kinds[mm] == "opaque" if mm >= 0 else False for mm in m_next])
        if opq.any():
            ids = active[opq]
            alb = np.array([solids[mm].albedo for mm in m_next[opq]])
            nn = nrm[opq]
            key = np.clip((nn @ np.array([-0.55, 0.62, 0.56]) / 1.0 + 0.3) / 1.3, 0, 1)
            fill = np.clip((nn @ np.array([0.7, 0.2, 0.68]) + 0.4) / 1.4, 0, 1)
            top = np.clip(nn[:, 1] * 0.5 + 0.5, 0, 1)
            shade = 0.22 + 0.75 * key + 0.18 * fill + 0.12 * top
            refl = d[opq] - 2 * np.sum(d[opq] * nn, 1)[:, None] * nn
            spec = 0.025 * env(refl)
            col[ids] += thr[ids] * (alb * shade[:, None] + spec)
            thr[ids] = 0
        keep = ~opq
        active, d, p, nrm, cosi, m_cur, m_next, new_inside = (active[keep], d[keep], p[keep], nrm[keep],
                                                               cosi[keep], m_cur[keep], m_next[keep], new_inside[keep])
        if active.size == 0:
            break
        n1 = iors[m_cur]; n2 = iors[m_next]
        eta = n1 / n2
        sint2 = eta ** 2 * (1 - cosi ** 2)
        tir = sint2 > 1
        cost = np.sqrt(np.clip(1 - sint2, 0, 1))
        rs = (n1 * cosi - n2 * cost) / (n1 * cosi + n2 * cost + 1e-12)
        rp = (n2 * cosi - n1 * cost) / (n2 * cosi + n1 * cost + 1e-12)
        F = np.where(tir, 1.0, (rs * rs + rp * rp) / 2)
        refl = d + 2 * cosi[:, None] * nrm
        contrib = thr[active] * F[:, None] * env(refl)
        if ev == 0:
            first[active] += contrib
        else:
            col[active] += np.where(tir[:, None], 0, contrib)
        refr = eta[:, None] * d + (eta * cosi - cost)[:, None] * nrm
        newd = np.where(tir[:, None], refl, refr)
        newd /= np.linalg.norm(newd, axis=1, keepdims=True)
        thr[active] *= np.where(tir, 1.0, 1 - F)[:, None]
        inside[active] = np.where(tir[:, None], inside[active], new_inside)
        D[active] = newd
        O[active] = p + newd * 3e-5
    if active.size:
        col[active] += thr[active] * transmit(D[active])
    return col, first, hit_any, saw_liquid


def camera_rays(w, h, cam, target, focal, extent_h, ss):
    W, H = w * ss, h * ss
    f = target - cam; f /= np.linalg.norm(f)
    right = np.cross(f, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, f)
    sx = extent_h * (w / h)
    u = (np.arange(W) + 0.5) / W * 2 - 1
    v = 1 - (np.arange(H) + 0.5) / H * 2
    U, V = np.meshgrid(u * sx / 2, v * extent_h / 2)
    D = f[None, None, :] * focal + U[..., None] * right + V[..., None] * up
    D = D.reshape(-1, 3)
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    O = np.tile(cam, (D.shape[0], 1)).astype(np.float64)
    return O, D, (W, H)


def project(pt, cam, target, focal, extent_h, w, h):
    f = target - cam; f /= np.linalg.norm(f)
    right = np.cross(f, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, f)
    v = np.array(pt) - cam
    z = v @ f
    sx = extent_h * (w / h)
    x = (v @ right) / z * focal
    y = (v @ up) / z * focal
    return ((x / (sx / 2)) + 1) / 2 * 100, (1 - y / (extent_h / 2)) / 2 * 100   # % of image


def render(solids, w, h, bg_hex, dark_scene, elev_deg=9.0, dist=11.0, center_y=1.35, extent_h=3.35, ss=2, chunk=160000):
    bg = hex_lin(bg_hex)
    env, transmit = make_env(bg, dark_scene)
    target = np.array([0.0, center_y, 0.0])
    e = math.radians(elev_deg)
    cam = target + dist * np.array([0.0, math.sin(e), math.cos(e)])
    focal = dist
    O, D, (W, H) = camera_rays(w, h, cam, target, focal, extent_h * 1.0, ss)
    col = np.zeros((D.shape[0], 3)); first = np.zeros_like(col)
    hit = np.zeros(D.shape[0], bool); liq = np.zeros(D.shape[0], bool)
    for s in range(0, D.shape[0], chunk):
        c, f1, hh, ll = trace(solids, O[s:s + chunk], D[s:s + chunk], env, transmit)
        col[s:s + chunk], first[s:s + chunk], hit[s:s + chunk], liq[s:s + chunk] = c, f1, hh, ll
    def down(x):
        x = x.reshape(H, W, -1).astype(np.float32)
        r = cv2.resize(x, (w, h), interpolation=cv2.INTER_AREA)
        return r if r.ndim == 3 and r.shape[2] > 1 else r.reshape(h, w)
    a = down(hit.astype(np.float32))
    colp = down(col * hit[:, None])
    firstp = down(first * hit[:, None])
    liqm = down((liq & hit).astype(np.float32))
    geo = dict(cam=cam, target=target, focal=focal, extent_h=extent_h, w=w, h=h)
    return colp, firstp, a, liqm, bg, geo


def tonemap(x):
    """soft shoulder so bright reflections roll off instead of clipping"""
    return np.where(x < 0.8, x, 0.8 + 0.2 * (1 - np.exp(-(x - 0.8) / 0.2)))


def finish(colp, a, bg):
    # colp is premultiplied by coverage; composite on the backdrop, then encode with alpha
    out = colp + (1 - a[..., None]) * bg
    out = lin_to_srgb(tonemap(out))
    bg_s = lin_to_srgb(bg)
    straight = (out - (1 - a[..., None]) * bg_s) / np.maximum(a[..., None], 1e-4)
    return np.clip(straight, 0, 1)


# ----------------------------------------------------------------------------
# bubbles
# ----------------------------------------------------------------------------
def bubble_sprite(size=96, hl=(-0.36, -0.40), seed=0):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    x, y = (xx - c) / (size * 0.46), (yy - c) / (size * 0.46)
    r = np.sqrt(x * x + y * y)
    inside = 1 - smoothstep(0.97, 1.02, r)
    rim = smoothstep(0.70, 0.95, r) * inside
    dark = np.exp(-((r - 0.80) / 0.07) ** 2) * inside
    h1 = np.exp(-(((x - hl[0]) ** 2 + (y - hl[1]) ** 2) / 0.018))
    h2 = np.exp(-(((x + hl[0] * 0.9) ** 2 + (y + hl[1] * 0.9) ** 2) / 0.05)) * 0.35
    # light caught on the lower rim (the bubble focuses light from above)
    crescent = np.clip((y - 0.1) / 0.9, 0, 1) * rim
    white = np.clip(0.06 * inside + 0.55 * rim + 0.5 * crescent + 0.95 * h1 + h2, 0, 1)
    black = np.clip(0.22 * dark - white * 0.3, 0, 1)
    a = np.clip(white + black, 0, 1)
    rgb = np.where(a[..., None] > 1e-4, (white / np.maximum(a, 1e-4))[..., None], 1) * np.ones(3)
    return rgb, a


def hero_bubble_sprite(size=72, hl=(-0.38, -0.40), ring=0.74):
    """Carbonation bubble for the coral hero, shown at 4-14 px.

    A thin bright meniscus ring, a deeper coral tone just inside it (so the edge
    reads against coral without a thick white outline), a crisp specular point and
    light focused onto the far rim. Mostly transparent in the middle. Normal alpha
    blending, so the deeper tone is kept (screen blending would drop it).
    """
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    c = (size - 1) / 2
    x, y = (xx - c) / (size * 0.47), (yy - c) / (size * 0.47)
    r = np.sqrt(x * x + y * y)
    inside = 1 - smoothstep(0.965, 1.0, r)
    ring_l = np.exp(-((r - 0.90) / 0.065) ** 2) * inside
    deep_l = np.exp(-((r - 0.74) / 0.09) ** 2) * inside
    spec = np.exp(-(((x - hl[0]) ** 2 + (y - hl[1]) ** 2) / 0.012))
    focus = np.clip((y + x * 0.35 - 0.05) / 0.8, 0, 1) * np.exp(-((r - 0.80) / 0.11) ** 2) * inside
    white = np.clip(0.10 * inside + ring * ring_l + 0.42 * focus + 0.95 * spec, 0, 1)
    shade = np.clip(0.40 * deep_l * (1 - white), 0, 1)
    a = np.clip(white + shade, 0, 1)
    deep = np.array([0x9E, 0x2E, 0x28]) / 255.0          # deeper coral, from #F46B62
    rgb = (white[..., None] + shade[..., None] * deep) / np.maximum(a[..., None], 1e-6)
    return np.clip(rgb, 0, 1).astype(np.float32), a.astype(np.float32)


def write_hero_bubbles():
    for i, (hl, ring) in enumerate([((-0.38, -0.40), 0.74), ((-0.30, -0.46), 0.68), ((-0.44, -0.30), 0.78)], 1):
        rgb, al = hero_bubble_sprite(72, hl, ring)
        save_rgba(os.path.join(OUT, f"bubble-{i}.webp"), rgb, al)
    print("bubble-1..3.webp written")


def main():
    if "--bubbles" in sys.argv:          # just the hero bubble sprites (fast)
        write_hero_bubbles()
        return
    os.makedirs(OUT, exist_ok=True)
    geo_out = {}

    # --- 1. the tumbler: water, drink, shine, mask (on forest green) ------------------
    water = dict(kind="liquid", ior=1.333, sigma_a=(0.05, 0.015, 0.03), name="water")
    drink = dict(kind="liquid", ior=1.34, sigma_a=(0.30, 0.05, 0.55), sigma_s=2.4,
                 scatter=(0.70, 0.86, 0.46), name="drink")
    W, H = 360, 480
    print("glass with water ...")
    solids_w, g = tumbler(level=1.95, liquid=water)
    col_w, first_w, a, liq, bg, cam = render(solids_w, W, H, "#174D3A", True)
    print("glass with drink ...")
    solids_d, _ = tumbler(level=1.95, liquid=drink)
    col_d, first_d, _, _, _, _ = render(solids_d, W, H, "#174D3A", True)

    save_rgba(os.path.join(OUT, "glass-water.webp"), finish(col_w, a, bg), a)
    save_rgba(os.path.join(OUT, "glass-drink.webp"), finish(col_d, a, bg), a)
    # shine: front reflections only, as light over whatever is beneath
    sh = tonemap(first_w)
    sh_a = np.clip(sh.max(axis=2) * 1.15, 0, 1)
    sh_rgb = lin_to_srgb(np.clip(sh / np.maximum(sh_a[..., None], 1e-4), 0, 1))
    save_rgba(os.path.join(OUT, "glass-shine.webp"), sh_rgb, sh_a)
    m = cv2.GaussianBlur(liq.astype(np.float32), (0, 0), 0.6)
    save_rgba(os.path.join(OUT, "glass-mask.webp"), np.ones(m.shape + (3,)), m)

    P = lambda pt: project(pt, cam["cam"], cam["target"], cam["focal"], cam["extent_h"], W, H)
    rin_level = g["r_bot"] + (g["r_top"] - g["r_bot"]) / g["H"] * g["level"] - g["wall"]
    geo_out["glass"] = {
        "surface_front_y": P((0, g["level"], rin_level))[1],
        "surface_back_y": P((0, g["level"], -rin_level))[1],
        "surface_left_x": P((-rin_level, g["level"], 0))[0],
        "surface_right_x": P((rin_level, g["level"], 0))[0],
        "base_front_y": P((0, g["base"], 0.75))[1],
        "base_center_y": P((0, g["base"], 0))[1],
        "rim_y": P((0, g["H"], 0))[1],
        "bottom_front_y": P((0, 0, g["r_bot"]))[1],
    }
    print("  glass geometry (% of image):", {k: round(v, 2) for k, v in geo_out["glass"].items()})

    # fine fizz on the drink surface, as a separate layer registered to the glass
    rng = np.random.default_rng(3)
    fz = np.zeros((H * 2, W * 2, 4), np.float32)
    g2 = geo_out["glass"]
    cx = (g2["surface_left_x"] + g2["surface_right_x"]) / 200 * W * 2
    rx = (g2["surface_right_x"] - g2["surface_left_x"]) / 200 * W * 2
    cy = (g2["surface_front_y"] + g2["surface_back_y"]) / 200 * H * 2
    ry = (g2["surface_front_y"] - g2["surface_back_y"]) / 200 * H * 2
    sprites = [bubble_sprite(64, hl, i) for i, hl in enumerate([(-0.36, -0.4), (-0.3, -0.45), (-0.42, -0.3)])]
    for _ in range(420):
        ang = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.uniform(0.15, 1.0)) * 0.97
        bx, by = cx + rx * rr * math.cos(ang), cy + ry * rr * math.sin(ang)
        s = int(rng.choice([3, 4, 4, 5, 6, 7, 9]))
        rgb, al = sprites[rng.integers(0, 3)]
        al_s = cv2.resize(al, (s, s), interpolation=cv2.INTER_AREA) * rng.uniform(0.55, 1.0)
        x0, y0 = int(bx - s / 2), int(by - s / 2)
        if x0 < 0 or y0 < 0 or x0 + s >= fz.shape[1] or y0 + s >= fz.shape[0]:
            continue
        region = fz[y0:y0 + s, x0:x0 + s]
        region[..., 3] = al_s + region[..., 3] * (1 - al_s)
        region[..., :3] = 1.0
    fz_a = cv2.resize(fz[..., 3], (W, H), interpolation=cv2.INTER_AREA)
    save_rgba(os.path.join(OUT, "glass-fizz.webp"), np.ones((H, W, 3)), np.clip(fz_a, 0, 1))

    # drink glass on the lifestyle arch colour (renders sit on their exact backdrop)
    print("drink glass for the lifestyle arch ...")
    col_a, first_a, a_a, _, bg_a, _ = render(solids_d, W, H, "#1E5A45", True)
    save_rgba(os.path.join(OUT, "glass-drink-arch.webp"), finish(col_a + first_a, a_a, bg_a), a_a)

    # --- 2. shot glass of amber ACV, on cream ------------------------------------------
    print("shot glass ...")
    amber = dict(kind="liquid", ior=1.34, sigma_a=(0.32, 1.05, 3.4), name="acv")
    shot, gs = tumbler(r_top=1.0, r_bot=0.78, H=1.75, wall=0.07, base=0.42, level=1.42, liquid=amber)
    col_s, first_s, a_s, _, bg_s, _ = render(shot, 300, 300, "#F6EBD3", False, elev_deg=12, center_y=0.86,
                                             extent_h=2.35, dist=9.0)
    save_rgba(os.path.join(OUT, "shot-amber.webp"), finish(col_s + first_s, a_s, bg_s), a_s)

    # --- 3. clay plinth -----------------------------------------------------------------
    print("plinth ...")
    pr, ph, b = 1.0, 0.36, 0.035
    prof = [(0.0, 0.0), (pr - b, 0.0)] + arc(pr - b, b, b, -math.pi / 2, 0, 5)[1:] + \
           [(pr, ph - b)] + arc(pr - b, ph - b, b, 0, math.pi / 2, 5)[1:] + [(0.0, ph)]
    clay = Solid(prof, "opaque", albedo=srgb_to_lin([0.93, 0.89, 0.80]), name="clay")
    PW, PH = 520, 200
    col_p, first_p, a_p, _, bg_p, camp = render([clay], PW, PH, "#1E5A45", True, elev_deg=11, center_y=0.12,
                                                extent_h=0.95, dist=12.0)
    rgb_p = lin_to_srgb(tonemap(col_p / np.maximum(a_p[..., None], 1e-4)))
    # contact shadow on the ground, under the plinth
    yy, xx = np.mgrid[0:PH, 0:PW].astype(np.float32)
    cxp, cyp = PW / 2, project((0, 0, 0), camp["cam"], camp["target"], camp["focal"], camp["extent_h"], PW, PH)[1] / 100 * PH
    ell = ((xx - cxp - 6) / (PW * 0.47)) ** 2 + ((yy - cyp - 3) / (PH * 0.07)) ** 2
    shadow = np.exp(-ell * 2.2) * 0.55
    alpha = a_p + shadow * (1 - a_p)
    rgb = (rgb_p * a_p[..., None]) / np.maximum(alpha[..., None], 1e-4)
    save_rgba(os.path.join(OUT, "plinth.webp"), rgb, alpha)
    pt = lambda q: project(q, camp["cam"], camp["target"], camp["focal"], camp["extent_h"], PW, PH)
    geo_out["plinth"] = {"top_center_y": pt((0, ph, 0))[1], "top_front_y": pt((0, ph, pr))[1],
                         "left_x": pt((-pr, ph, 0))[0], "right_x": pt((pr, ph, 0))[0]}
    print("  plinth geometry (% of image):", {k: round(v, 2) for k, v in geo_out["plinth"].items()})

    # --- 4. hero bubble sprites ---------------------------------------------------------
    write_hero_bubbles()

    with open(os.path.join(ROOT, "tools", "props-geometry.json"), "w") as f:
        json.dump(geo_out, f, indent=2)


if __name__ == "__main__":
    main()

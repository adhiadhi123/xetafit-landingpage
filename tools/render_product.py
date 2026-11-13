"""
XETAFIT product renderer
========================
Builds every product image the landing page uses from ONE front packshot of the
tube on a white studio background, so all sections show the same product, light
and material.

    python tools/render_product.py [front_packshot.png] [--tubes | --tablets]

    --tubes    only the tube views, shadows and four-pack (about 30 s)
    --tablets  only the two tablets

Default source: assets/source/xetafit-tube-front.png
Requires: numpy, pillow, opencv-python(-headless)

Outputs (assets/images/)
------------------------
  tube-front.webp        master front view: anti-aliased geometric matte, white fringe removed
  tube-angle.webp        the same tube turned about its own axis (label re-projected in 3D)
  tube-tilt.webp         the turned tube leaning, for floating compositions
  tube-shadow.webp       ground shadow lifted from the studio shot (contact line + soft falloff)
  tube-shadow-soft.webp  the same shadow diffused, for the floating hero tube
  pack4.webp             four tubes in a receding row, with ground shadows and
                         occlusion shadows between the tubes
  tablet-a.webp, tablet-b.webp, tablet-c.webp   effervescent tablets ray-marched in 3D
                         (pale mint, chalky, porous, green flecks)

How the turned views are made
-----------------------------
The tube is a surface of revolution: its outline, cap and base look identical at
any rotation, and only the printed label moves. For a label pixel seen at camera
angle theta, the script reads the label point phi = theta + alpha from the source.
It divides out the studio shading the source had at phi (measured from the white
label areas), then applies the shading at theta. The lights therefore stay fixed
in the studio while the tube turns, like a turntable shot. Label areas the source
never showed (|phi| > ~68 deg) continue each row's own band colour.

The geometry is measured automatically from the source (body edges, cap rows, the
contact line under the base), so a new packshot with the same set-up re-renders
everything. Measurements are printed; check them if you change the source.
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
DEFAULT_SRC = os.path.join(ROOT, "assets", "source", "xetafit-tube-front.png")

ANGLE_DEG = 24.0          # tube-angle.webp: turn about the axis
TILT_DEG = -24.0          # tube-tilt.webp: lean (negative = top leans right)
PACK_TURNS = (-5.0, 6.0, 13.0, 19.0)   # label turn of each tube, front to back
PHI_REAL = math.radians(63)            # label data trusted up to here ...
PHI_FILL = math.radians(70)            # ... fully band-coloured from here
SIN_EPS = 0.12            # camera elevation (label rows bend slightly with rotation)


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def save_rgba(path, rgb, alpha, quality=92):
    """rgb, alpha: float arrays 0..1 (straight alpha). Crops to content."""
    ys, xs = np.where(alpha > 0.002)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = np.dstack([rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]])
    img = Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    img.save(path, "WEBP", quality=quality, method=6, alpha_quality=100)
    print(f"  wrote {os.path.relpath(path, ROOT)}  {img.size[0]}x{img.size[1]}  {os.path.getsize(path)//1024} KB")
    return (x0, y0, x1, y1)


def premul(rgb, a):
    return rgb * a[..., None]


def unpremul(prgb, a):
    return np.where(a[..., None] > 1e-4, prgb / np.maximum(a[..., None], 1e-4), 0)


# ----------------------------------------------------------------------------
# 1. measure the packshot
# ----------------------------------------------------------------------------
def measure(a):
    H, W, _ = a.shape
    border = np.concatenate([a[:12].reshape(-1, 3), a[:, :12].reshape(-1, 3), a[:, -12:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    d = np.abs(a - bg).max(axis=2)
    obj = d > 0.035
    lum = a.mean(axis=2)

    # body edges (mid height), with sub-pixel coverage of the outermost pixels
    bgl = float(bg.mean())
    L, Rr = [], []
    for y in range(int(H * 0.3), int(H * 0.8), 3):
        xs = np.where(obj[y])[0]
        if len(xs) < 10:
            continue
        l, r = xs.min(), xs.max()
        cl = np.clip((bgl - lum[y, l]) / max(bgl - lum[y, l + 2], 0.05), 0, 1)
        cr = np.clip((bgl - lum[y, r]) / max(bgl - lum[y, r - 2], 0.05), 0, 1)
        L.append(l + 1 - cl); Rr.append(r + cr)
    xl, xr = float(np.median(L)), float(np.median(Rr))
    x0 = (xl + xr) / 2.0
    R = (xr - xl) / 2.0

    # cap: rows from the first object row until the outline narrows to the body
    rows_obj = np.where(obj[:, int(x0)])[0]
    cap_top = int(rows_obj.min())
    body_start = None
    for y in range(cap_top + 20, int(H * 0.4)):
        xs = np.where(obj[y])[0]
        if len(xs) and xs.min() >= xl - 1.5 and xs.max() <= xr + 1.5:
            # require 5 consecutive body-width rows
            ok = True
            for k in range(1, 6):
                xs2 = np.where(obj[y + k])[0]
                ok &= bool(len(xs2)) and xs2.min() >= xl - 1.5 and xs2.max() <= xr + 1.5
            if ok:
                body_start = y
                break

    # contact line under the base: darkest pixel per column in the bottom band
    cols = np.arange(int(x0 - R * 0.95), int(x0 + R * 0.95))
    y_lo, y_hi = int(H * 0.915), int(H * 0.985)
    yc = np.array([y_lo + np.argmin(lum[y_lo:y_hi, x]) for x in cols], float)
    c = np.sqrt(np.clip(1 - ((cols + 0.5 - x0) / R) ** 2, 0, 1))
    A = np.vstack([np.ones_like(c), c]).T
    (Yb, Kb), *_ = np.linalg.lstsq(A, yc, rcond=None)
    resid = np.abs(yc - A @ np.array([Yb, Kb]))
    keep = resid < 3
    (Yb, Kb), *_ = np.linalg.lstsq(A[keep], yc[keep], rcond=None)
    Yb -= 1.0   # last tube row sits just above the contact line

    # top of the cap: an ellipse (camera slightly above); fit to the first object row per column
    cap_l = min(np.where(obj[y])[0].min() for y in range(cap_top + 15, body_start))
    cap_r = max(np.where(obj[y])[0].max() for y in range(cap_top + 15, body_start))
    ccx, crx = (cap_l + cap_r + 1) / 2.0, (cap_r - cap_l + 1) / 2.0
    tc = np.arange(int(ccx - crx * 0.85), int(ccx + crx * 0.85))
    first = np.array([np.argmax(d[:, x] > 0.035) for x in tc])
    cov = np.array([np.clip(d[f, x] / max(d[f + 2, x], 0.05), 0, 1) for f, x in zip(first, tc)])
    ty = first + 1 - cov
    cc = np.sqrt(np.clip(1 - ((tc + 0.5 - ccx) / crx) ** 2, 0, 1))
    A2 = np.vstack([np.ones_like(cc), cc]).T
    (Yt, Kt), *_ = np.linalg.lstsq(A2, ty, rcond=None)

    geo = dict(H=H, W=W, bg=bg.tolist(), x0=x0, R=R, cap_top=cap_top, body_start=body_start,
               base_y=Yb, base_k=Kb, cap_cx=ccx, cap_rx=crx, cap_cy=Yt, cap_ry=-Kt)
    print("  geometry:", json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in geo.items() if k != 'bg'}))
    return geo, d, obj


# ----------------------------------------------------------------------------
# 2. matte (alpha) of the tube, shared by every rotation
# ----------------------------------------------------------------------------
def tube_alpha(a, geo, d, obj):
    H, W = geo["H"], geo["W"]
    x0, R = geo["x0"], geo["R"]
    X = np.arange(W)[None, :] + 0.0
    Y = np.arange(H)[:, None] + 0.0

    # body + base: analytic cylinder outline with an elliptic bottom
    cov_x = np.clip(np.minimum(X + 1, x0 + R) - np.maximum(X, x0 - R), 0, 1)
    cx = np.sqrt(np.clip(1 - ((X + 0.5 - x0) / R) ** 2, 0, 1))
    y_bot = geo["base_y"] + geo["base_k"] * cx
    # small rounded corner where the base meets the ground
    fil = 5.0
    edge_dist = R - np.abs(X + 0.5 - x0)
    y_bot = y_bot - np.where(edge_dist < fil, fil - np.sqrt(np.clip(fil ** 2 - (fil - edge_dist) ** 2, 0, None)), 0)
    cov_y = np.clip(y_bot - Y, 0, 1)
    body = cov_x * cov_y * (Y >= geo["body_start"] - 2)

    # cap: per-row outline (sub-pixel) intersected with the elliptic top
    cap = np.zeros((H, W), np.float32)
    y_a, y_b = geo["cap_top"] - 1, geo["body_start"] + 3
    xl = np.full(H, np.nan); xr = np.full(H, np.nan)
    for y in range(int(geo["cap_cy"]), y_b):
        xs = np.where(obj[y])[0]
        if len(xs) < 10:
            continue
        l, r = xs.min(), xs.max()
        xl[y] = l + 1 - np.clip(d[y, l] / max(d[y, l + 2], 0.05), 0, 1)
        xr[y] = r + np.clip(d[y, r] / max(d[y, r - 2], 0.05), 0, 1)
    rows = np.arange(int(geo["cap_cy"]), y_b)
    xl[rows] = cv2.medianBlur(np.nan_to_num(xl[rows], nan=geo["cap_cx"] - geo["cap_rx"]).astype(np.float32).reshape(-1, 1), 5).ravel()
    xr[rows] = cv2.medianBlur(np.nan_to_num(xr[rows], nan=geo["cap_cx"] + geo["cap_rx"]).astype(np.float32).reshape(-1, 1), 5).ravel()
    xl[y_a:int(geo["cap_cy"])] = xl[int(geo["cap_cy"])]
    xr[y_a:int(geo["cap_cy"])] = xr[int(geo["cap_cy"])]
    cc = np.sqrt(np.clip(1 - ((X + 0.5 - geo["cap_cx"]) / geo["cap_rx"]) ** 2, 0, 1))
    y_top = geo["cap_cy"] - geo["cap_ry"] * cc
    y_top = np.where(cc > 0, y_top, H)
    for y in range(y_a, y_b):
        if np.isnan(xl[y]):
            continue
        covx = np.clip(np.minimum(X[0] + 1, xr[y]) - np.maximum(X[0], xl[y]), 0, 1)
        covy = np.clip(y + 1 - y_top[0], 0, 1)
        cap[y] = covx * covy
    return np.maximum(body, cap).astype(np.float32)


def decontaminate(a, alpha, bg):
    al = alpha[..., None]
    rgb = (a - (1 - al) * bg[None, None, :]) / np.maximum(al, 1e-3)
    rgb = np.clip(rgb, 0, 1)
    # where alpha is tiny the estimate is noise: take the colour 2 px inwards
    near = cv2.blur(premul(np.where(al > 0.6, rgb, 0), (alpha > 0.6).astype(np.float32)), (5, 5))
    w = cv2.blur((alpha > 0.6).astype(np.float32), (5, 5))[..., None]
    fallback = np.where(w > 1e-3, near / np.maximum(w, 1e-3), rgb)
    return np.where(al < 0.35, fallback, rgb)


# ----------------------------------------------------------------------------
# 3. ground shadow from the studio shot
# ----------------------------------------------------------------------------
def ground_shadow(a, geo, alpha):
    H, W = geo["H"], geo["W"]
    lum = a.mean(axis=2)
    bgl = float(np.mean(geo["bg"]))
    sh = np.clip((bgl - lum) / bgl, 0, 1)
    region = np.zeros((H, W), np.float32)
    top = int(geo["base_y"] - 30)
    x0, R = geo["x0"], geo["R"]
    region[top:, int(max(0, x0 - 2.6 * R)):int(min(W, x0 + 2.6 * R))] = 1
    sh = sh * region * (1 - alpha)
    # fill the part hidden behind the tube so the shadow also works when the tube lifts
    hole = ((alpha > 0.02) & (region > 0)).astype(np.uint8)
    sh8 = (np.clip(sh * 1.6, 0, 1) * 255).astype(np.uint8)
    filled = cv2.inpaint(sh8, hole, 9, cv2.INPAINT_TELEA).astype(np.float32) / 255 / 1.6
    filled = cv2.GaussianBlur(filled, (0, 0), 0.8)
    # fade the far edges of the crop
    filled *= smoothstep(H - 1, H - 25, np.arange(H))[:, None]
    soft = cv2.GaussianBlur(filled, (0, 0), R * 0.16) * 0.75
    return filled, soft


# ----------------------------------------------------------------------------
# 4. turning the label about the axis
# ----------------------------------------------------------------------------
def shading_profile(a, geo):
    """Per-column studio shading of white label paper, as a function of theta."""
    H = geo["H"]
    x0, R = geo["x0"], geo["R"]
    cols = np.arange(int(math.floor(x0 - R)), int(math.ceil(x0 + R)))
    rows = slice(int(H * 0.25), int(H * 0.62))
    S = np.full((len(cols), 3), np.nan, np.float32)
    for i, x in enumerate(cols):
        px = a[rows, x]
        lum = px.mean(axis=1)
        neutral = (np.ptp(px, axis=1) < 0.04) & (lum > 0.55)
        if neutral.sum() > 12:
            # upper part of the distribution = clean paper (text / shadows are darker)
            sel = px[neutral]
            thr = np.percentile(sel.mean(axis=1), 60)
            S[i] = np.median(sel[sel.mean(axis=1) >= thr], axis=0)
    good = ~np.isnan(S[:, 0])
    idx = np.arange(len(cols))
    for ch in range(3):
        S[:, ch] = np.interp(idx, idx[good], S[good, ch])
        S[:, ch] = cv2.GaussianBlur(S[:, ch].reshape(-1, 1), (1, 0), sigmaX=1, sigmaY=2.2).ravel()
    th = np.arcsin(np.clip((cols + 0.5 - x0) / R, -1, 1))
    return th, np.maximum(S, 0.05)


def eval_S(th_tab, S_tab, th):
    out = np.empty(th.shape + (3,), np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(th, th_tab, S_tab[:, ch])
    return out


def turn_tube(a, geo, alpha_rad, th_tab, S_tab):
    H, W = geo["H"], geo["W"]
    x0, R = geo["x0"], geo["R"]
    out = a.copy()
    y0 = geo["body_start"] + 3
    y1 = int(geo["base_y"] - 2)
    xs = np.arange(W) + 0.5
    u = (xs - x0) / R
    inside = np.abs(u) < 1
    th = np.arcsin(np.clip(u, -1, 1))
    phi = th + alpha_rad
    phi_c = np.clip(phi, -PHI_FILL, PHI_FILL)

    # albedo of the source = source / its own shading
    S_src_cols = eval_S(th_tab, S_tab, th)                    # shading at each source column
    alb_src = a / S_src_cols[None, :, :]

    # each row's band colour, taken from the same side of the label (56-66 deg) so the
    # hidden side continues whatever the visible edge shows in that row
    # Only label-background pixels count (paper white or label green); artwork such as the
    # pomegranate is skipped and the band is interpolated across it vertically.
    def side_band(sign):
        sel = inside & (sign * th > math.radians(38)) & (sign * th < math.radians(64))
        px = alb_src[:, sel, :]
        c = np.clip(px, 0, 1)
        mx, mn = c.max(-1), c.min(-1)
        sat = (mx - mn) / (mx + 1e-6)
        white = (mn > 0.8) & (sat < 0.12)
        green = (c[..., 1] > c[..., 0] + 0.08) & (c[..., 1] > c[..., 2] + 0.2) & (mx > 0.45)
        ok = white | green
        b = np.full((px.shape[0], 3), np.nan, np.float32)
        for y in range(px.shape[0]):
            if ok[y].sum() >= 4:
                # use the outermost background pixels of the row (closest to the hidden side)
                idx = np.where(ok[y])[0]
                idx = idx[-6:] if sign > 0 else idx[:6]
                b[y] = np.median(px[y, idx], axis=0)
        yy = np.arange(px.shape[0])
        for ch in range(3):
            good = ~np.isnan(b[:, ch])
            b[:, ch] = np.interp(yy, yy[good], b[good, ch])
        b8 = (np.clip(b, 0, 4) * 60).astype(np.uint8).reshape(-1, 1, 3)
        return cv2.medianBlur(b8, 9).reshape(-1, 3).astype(np.float32) / 60.0
    band_r, band_l = side_band(1), side_band(-1)

    rows = np.arange(y0, y1)
    map_x = np.broadcast_to(x0 + R * np.sin(phi_c) - 0.5, (len(rows), W)).astype(np.float32)
    shift = R * SIN_EPS * (np.cos(phi_c) - np.cos(th))
    map_y = (rows[:, None] + shift[None, :]).astype(np.float32)
    alb_map = cv2.remap(alb_src.astype(np.float32), map_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    w = smoothstep(PHI_REAL, PHI_FILL, np.abs(phi))[None, :, None]
    band = np.where((phi > 0)[None, :, None], band_r[rows][:, None, :], band_l[rows][:, None, :])
    alb = alb_map * (1 - w) + band * w
    shaded = alb * eval_S(th_tab, S_tab, th)[None, :, :]
    region = inside[None, :] & np.ones((len(rows), 1), bool)
    out[y0:y1][region] = np.clip(shaded, 0, 1)[region]
    return out


# ----------------------------------------------------------------------------
# 5. compositing helpers
# ----------------------------------------------------------------------------
def crop_rgba(rgb, alpha, pad=0):
    ys, xs = np.where(alpha > 0.002)
    y0, y1 = max(ys.min() - pad, 0), ys.max() + 1 + pad
    x0, x1 = max(xs.min() - pad, 0), xs.max() + 1 + pad
    return rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1], (x0, y0)


def rotate_rgba(rgb, alpha, deg):
    h, w = alpha.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos) + 4, int(h * cos + w * sin) + 4
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    pm = premul(rgb, alpha).astype(np.float32)
    pm_r = cv2.warpAffine(pm, M, (nw, nh), flags=cv2.INTER_LANCZOS4, borderValue=0)
    a_r = cv2.warpAffine(alpha.astype(np.float32), M, (nw, nh), flags=cv2.INTER_LANCZOS4, borderValue=0)
    a_r = np.clip(a_r, 0, 1)
    return np.clip(unpremul(np.clip(pm_r, 0, None), a_r), 0, 1), a_r


def scale_rgba(prgb, alpha, s):
    h, w = alpha.shape
    size = (max(1, int(round(w * s))), max(1, int(round(h * s))))
    return cv2.resize(prgb, size, interpolation=cv2.INTER_AREA), cv2.resize(alpha, size, interpolation=cv2.INTER_AREA)


# ----------------------------------------------------------------------------
# 6. effervescent tablet, ray-marched
# ----------------------------------------------------------------------------
def value_noise(shape, scale, rng):
    h, w = shape
    g = rng.random((int(h / scale) + 3, int(w / scale) + 3)).astype(np.float32)
    return cv2.resize(g, (w + int(3 * scale), h + int(3 * scale)), interpolation=cv2.INTER_CUBIC)[:h, :w]


def tablet_textures(rng, n=1024):
    """Albedo + height maps for the face (n x n, uv in [-1,1]) and the edge strip."""
    def fbm(shape):
        return (0.5 * value_noise(shape, 90, rng) + 0.28 * value_noise(shape, 30, rng)
                + 0.14 * value_noise(shape, 9, rng) + 0.08 * value_noise(shape, 3, rng))

    def make(shape, flecks, pores):
        h, w = shape
        base_a = np.array([0.800, 0.895, 0.700], np.float32)   # pale mint
        base_b = np.array([0.715, 0.840, 0.600], np.float32)
        n1 = fbm(shape)
        alb = base_a * (1 - n1[..., None]) + base_b * n1[..., None]
        height = 0.6 * n1 + 0.4 * value_noise(shape, 2, rng)
        # porous pits: small dark-ish dents
        pit = np.zeros(shape, np.float32)
        ys, xs = rng.integers(0, h, pores), rng.integers(0, w, pores)
        rs = rng.uniform(0.8, 2.6, pores)
        for y, x, r in zip(ys, xs, rs):
            cv2.circle(pit, (int(x), int(y)), int(round(r)), float(rng.uniform(0.5, 1.0)), -1, lineType=cv2.LINE_AA)
        pit = cv2.GaussianBlur(pit, (0, 0), 0.7)
        alb *= (1 - 0.20 * pit[..., None])
        height -= 1.2 * pit
        # green flecks (flavour granules)
        fl = np.zeros(shape, np.float32)
        ys, xs = rng.integers(0, h, flecks), rng.integers(0, w, flecks)
        for y, x in zip(ys, xs):
            r = rng.uniform(0.6, 2.0)
            cv2.ellipse(fl, (int(x), int(y)), (max(1, int(r * 1.4)), max(1, int(r))), float(rng.uniform(0, 180)),
                        0, 360, float(rng.uniform(0.45, 1.0)), -1, lineType=cv2.LINE_AA)
        fl = cv2.GaussianBlur(fl, (0, 0), 0.6)
        fleck_col = np.array([0.40, 0.64, 0.20], np.float32)
        alb = alb * (1 - 0.85 * fl[..., None]) + fleck_col * 0.85 * fl[..., None]
        height += 0.25 * fl
        return np.clip(alb, 0, 1), cv2.GaussianBlur(height, (0, 0), 0.6)

    face = make((n, n), flecks=4200, pores=7000)
    edge = make((n // 4, n * 3), flecks=1400, pores=3400)
    return face, edge


def sdf_tablet(p, r, h, k):
    q = np.sqrt(p[..., 0] ** 2 + p[..., 2] ** 2)
    dx = q - r + k
    dy = np.abs(p[..., 1]) - h + k
    out = np.minimum(np.maximum(dx, dy), 0) + np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2) - k
    return out


def rot(ax, ay, az):
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def render_tablet(path, tilt_deg, roll_deg, spin_deg, seed, size=560, ss=2):
    rng = np.random.default_rng(seed)
    (f_alb, f_h), (e_alb, e_h) = tablet_textures(rng)
    r, h, k = 1.0, 0.24, 0.07
    N = size * ss
    span = 1.32
    xs = np.linspace(-span, span, N, dtype=np.float32)
    X, Y = np.meshgrid(xs, -xs)
    # world -> local: tablet rotated by tilt (around x), spin (around its own axis), roll (around view axis)
    M = (rot(math.radians(tilt_deg), 0, math.radians(roll_deg)) @ rot(0, math.radians(spin_deg), 0)).astype(np.float32)
    Minv = M.T
    ro = np.stack([X, Y, np.full_like(X, 4.0)], -1).reshape(-1, 3)
    rd = np.array([0, 0, -1.0], np.float32)
    ro_l = ro @ M                      # world -> local (row vectors)
    rd_l = rd @ M
    t = np.full(ro.shape[0], 2.0, np.float32)
    active = np.arange(ro.shape[0])
    for it in range(80):               # sphere tracing, only on rays still marching
        p = ro_l[active] + t[active, None] * rd_l
        dist = sdf_tablet(p, r, h, k)
        t[active] += dist * 0.92
        keep = (dist > 1e-4) & (t[active] < 6.5)
        active = active[keep]
        if active.size == 0:
            break
    t = t.reshape(X.shape)
    ro_l = ro_l.reshape(X.shape + (3,))
    p = ro_l + t[..., None] * rd_l
    dist = sdf_tablet(p, r, h, k)
    mask = (np.abs(dist) < 3e-3) & (t < 7)
    e = 1e-3
    n = np.stack([
        sdf_tablet(p + [e, 0, 0], r, h, k) - sdf_tablet(p - [e, 0, 0], r, h, k),
        sdf_tablet(p + [0, e, 0], r, h, k) - sdf_tablet(p - [0, e, 0], r, h, k),
        sdf_tablet(p + [0, 0, e], r, h, k) - sdf_tablet(p - [0, 0, e], r, h, k)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9

    # texture lookup: face (top/bottom) vs edge band
    on_face = np.abs(n[..., 1]) > 0.55
    fn = f_alb.shape[0]
    fu = ((p[..., 0] / r) * 0.5 + 0.5) * (fn - 1)
    fv = ((p[..., 2] / r) * 0.5 + 0.5) * (fn - 1)
    ang = np.arctan2(p[..., 2], p[..., 0])
    eu = (ang / (2 * math.pi) + 0.5) * (e_alb.shape[1] - 1)
    ev = ((p[..., 1] / h) * 0.5 + 0.5) * (e_alb.shape[0] - 1)
    def samp(img, u, v):
        return cv2.remap(img, u.astype(np.float32), v.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    alb = np.where(on_face[..., None], samp(f_alb, fu, fv), samp(e_alb, eu, ev))
    # bump from height map gradients (in texture space)
    fhx, fhy = cv2.Sobel(f_h, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(f_h, cv2.CV_32F, 0, 1, ksize=3)
    ehx, ehy = cv2.Sobel(e_h, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(e_h, cv2.CV_32F, 0, 1, ksize=3)
    gx = np.where(on_face, samp(fhx, fu, fv), samp(ehx, eu, ev))
    gy = np.where(on_face, samp(fhy, fu, fv), samp(ehy, eu, ev))

    # normals to world space, perturbed by the bump gradient
    n_w = (n @ M.T).astype(np.float32)
    tx_l = np.where(on_face[..., None], np.array([1, 0, 0], np.float32), np.stack([-np.sin(ang), np.zeros_like(ang), np.cos(ang)], -1))
    ty_l = np.where(on_face[..., None], np.array([0, 0, 1], np.float32), np.array([0, 1, 0], np.float32))
    tx_w, ty_w = tx_l @ M.T, ty_l @ M.T
    bump = 0.8
    n_w = n_w - bump * (gx[..., None] * tx_w + gy[..., None] * ty_w)
    n_w /= np.linalg.norm(n_w, axis=-1, keepdims=True) + 1e-9

    # studio lighting matching the tube: soft key from upper left, fill right, top bounce
    def lam(L, wrap):
        L = np.array(L, np.float32); L /= np.linalg.norm(L)
        return np.clip((n_w @ L + wrap) / (1 + wrap), 0, 1)
    key = lam([-0.55, 0.62, 0.56], 0.35)
    fill = lam([0.75, 0.1, 0.65], 0.5)
    top = lam([0, 1, 0.2], 0.6)
    rim = np.clip(1 - n_w[..., 2], 0, 1) ** 3
    # ambient occlusion from the SDF along the normal
    p_w = (p @ M.T).astype(np.float32)
    ao = np.ones(X.shape, np.float32)
    for i, s in enumerate((0.02, 0.05, 0.1)):
        q = (p_w + n_w * s) @ Minv.T
        ao -= (s - np.maximum(sdf_tablet(q, r, h, k), 0)) * (2.2 / (i + 1))
    ao = np.clip(ao, 0.55, 1)
    light = 0.27 * ao + 0.70 * key + 0.16 * fill + 0.11 * top
    col = alb * light[..., None] + 0.04 * rim[..., None]
    spec_L = np.array([-0.45, 0.6, 0.66], np.float32); spec_L /= np.linalg.norm(spec_L)
    hv = spec_L + np.array([0, 0, 1], np.float32); hv /= np.linalg.norm(hv)
    col += 0.035 * (np.clip(n_w @ hv, 0, 1) ** 18)[..., None]
    col = 1 - np.exp(-col * 1.1)             # gentle filmic shoulder
    col = col / (1 - math.exp(-1.1))
    col = np.clip(col, 0, 1)
    # anti-aliased coverage via supersampling
    a_ss = mask.astype(np.float32)
    rgb = cv2.resize(premul(col, a_ss).astype(np.float32), (size, size), interpolation=cv2.INTER_AREA)
    al = cv2.resize(a_ss, (size, size), interpolation=cv2.INTER_AREA)
    save_rgba(path, unpremul(rgb, al), al)


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    flags = {x for x in sys.argv[1:] if x.startswith("--")}
    do_tubes = "--tablets" not in flags
    do_tablets = "--tubes" not in flags
    if do_tablets and not do_tubes:
        render_tablets()
        return
    src = args[0] if args else DEFAULT_SRC
    print("source:", os.path.relpath(src, ROOT) if src.startswith(ROOT) else src)
    a = np.asarray(Image.open(src).convert("RGB")).astype(np.float32) / 255.0
    geo, d, obj = measure(a)
    bg = np.array(geo["bg"], np.float32)
    alpha = tube_alpha(a, geo, d, obj)
    sh, sh_soft = ground_shadow(a, geo, alpha)
    th_tab, S_tab = shading_profile(a, geo)

    # front master
    front = decontaminate(a, alpha, bg)
    box_front = save_rgba(os.path.join(OUT, "tube-front.webp"), front, alpha)

    # shadows, cropped to a box centred on the tube; report placement relative to the tube image
    def save_shadow(name, s, strength):
        s = np.clip(s * strength, 0, 1)
        box = save_rgba(os.path.join(OUT, name), np.zeros(s.shape + (3,), np.float32) + 0.04, s)
        tw, th = box_front[2] - box_front[0], box_front[3] - box_front[1]
        place = dict(left=(box[0] - box_front[0]) / tw * 100, width=(box[2] - box[0]) / tw * 100,
                     top=(box[1] - box_front[1]) / th * 100, height=(box[3] - box[1]) / th * 100)
        print("    placement vs tube box (%):", {k: round(v, 2) for k, v in place.items()})
        return place
    place_hard = save_shadow("tube-shadow.webp", sh, 1.0)
    place_soft = save_shadow("tube-shadow-soft.webp", sh_soft, 1.0)
    with open(os.path.join(ROOT, "tools", "render-placement.json"), "w") as f:
        json.dump({"tube_shadow": place_hard, "tube_shadow_soft": place_soft}, f, indent=2)

    # turned view
    turned = turn_tube(a, geo, math.radians(ANGLE_DEG), th_tab, S_tab)
    angle_rgb = decontaminate(turned, alpha, bg)
    save_rgba(os.path.join(OUT, "tube-angle.webp"), angle_rgb, alpha)

    # leaning view (from the turned tube)
    c_rgb, c_a, _ = crop_rgba(angle_rgb, alpha, pad=4)
    t_rgb, t_a = rotate_rgba(c_rgb, c_a, TILT_DEG)
    save_rgba(os.path.join(OUT, "tube-tilt.webp"), t_rgb, t_a)

    # four-pack: back to front, each with its ground shadow and an occlusion shadow on the tubes behind
    scales = (1.0, 0.935, 0.875, 0.82)
    tw = (box_front[2] - box_front[0])
    canvas_w, canvas_h = int(tw * 3.5), int(geo["H"] * 1.02)
    prgb = np.zeros((canvas_h, canvas_w, 3), np.float32)
    pa = np.zeros((canvas_h, canvas_w), np.float32)
    base_y0 = canvas_h - 70
    placements = []
    x_cursor = 40
    for i, s in enumerate(scales):
        placements.append((x_cursor, base_y0 - i * 34, s))
        x_cursor += int(tw * s * 0.74)
    for i in reversed(range(4)):
        x_left, base_y, s = placements[i]
        rgb_i = decontaminate(turn_tube(a, geo, math.radians(PACK_TURNS[i]), th_tab, S_tab), alpha, bg) if PACK_TURNS[i] else front
        # crop tube + its shadow area together so they stay registered
        y_top = geo["cap_top"] - 4
        y_bot = geo["H"]
        x_l = int(geo["x0"] - 2.6 * geo["R"]); x_r = int(geo["x0"] + 2.6 * geo["R"])
        t_pm = premul(rgb_i, alpha)[y_top:y_bot, x_l:x_r]
        t_a = alpha[y_top:y_bot, x_l:x_r]
        s_a = np.clip(sh[y_top:y_bot, x_l:x_r] * 0.9, 0, 1)
        t_pm, t_a = scale_rgba(t_pm.astype(np.float32), t_a.astype(np.float32), s)
        s_a = cv2.resize(s_a, (t_a.shape[1], t_a.shape[0]), interpolation=cv2.INTER_AREA)
        # anchor: bottom of the tube at base_y, left of the tube body at x_left
        tube_left_in_crop = (geo["x0"] - geo["R"] - x_l) * s
        tube_bottom_in_crop = (geo["base_y"] + geo["base_k"] - y_top) * s
        ox = int(round(x_left - tube_left_in_crop)); oy = int(round(base_y - tube_bottom_in_crop))
        h_, w_ = t_a.shape
        ys, xs = slice(max(oy, 0), min(oy + h_, canvas_h)), slice(max(ox, 0), min(ox + w_, canvas_w))
        cy, cx = slice(ys.start - oy, ys.stop - oy), slice(xs.start - ox, xs.stop - ox)
        # occlusion shadow this tube throws on the tubes already drawn (light from the left)
        occ = np.zeros((canvas_h, canvas_w), np.float32)
        occ[ys, xs] = t_a[cy, cx]
        shift = int(tw * s * 0.07)
        occ = np.roll(occ, shift, axis=1)
        occ = cv2.GaussianBlur(occ, (0, 0), tw * s * 0.06) * 0.42
        prgb *= (1 - occ[..., None])
        # ground shadow (darkens what is behind, adds shadow alpha on empty ground)
        sa = np.zeros((canvas_h, canvas_w), np.float32)
        sa[ys, xs] = s_a[cy, cx]
        prgb = prgb * (1 - sa[..., None])
        pa = pa + sa * (1 - pa)
        # the tube itself
        ta = np.zeros((canvas_h, canvas_w), np.float32); tp = np.zeros_like(prgb)
        ta[ys, xs] = t_a[cy, cx]; tp[ys, xs] = t_pm[cy, cx]
        prgb = tp + prgb * (1 - ta[..., None])
        pa = ta + pa * (1 - ta)
    save_rgba(os.path.join(OUT, "pack4.webp"), unpremul(prgb, pa), pa)

    if do_tablets:
        render_tablets()


def render_tablets():
    print("  rendering tablets ...")
    render_tablet(os.path.join(OUT, "tablet-a.webp"), tilt_deg=58, roll_deg=-18, spin_deg=20, seed=7)
    render_tablet(os.path.join(OUT, "tablet-b.webp"), tilt_deg=34, roll_deg=24, spin_deg=110, seed=11)
    # lying flat, seen from the same low camera as the plinth (lifestyle arch)
    render_tablet(os.path.join(OUT, "tablet-c.webp"), tilt_deg=13, roll_deg=-3, spin_deg=40, seed=13)


if __name__ == "__main__":
    main()

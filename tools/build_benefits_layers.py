"""Builds the layers for the 05 Benefits opening animation (cap unscrews, one tablet rises).

    python tools/build_benefits_layers.py            # tube, inner wall, cap frames + tablet strip (~2 min)
    python tools/build_benefits_layers.py --fast     # skip the tablet strip
    python tools/build_benefits_layers.py --css      # only rewrite the motion in css/benefits.css

Why this exists
---------------
The studio packshot (assets/source/xetafit-tube-front.png) is seen from roughly the middle
of the tube: the base curves like a smile (seen from above) but every edge of the cap
curves like a frown (seen from below). From that viewpoint the mouth of an open tube is
physically invisible, so an "open tube" cannot be cut out of the photo. The rim, the
inside of the tube and the top of the cap only become visible from a camera above the
product. This script therefore builds one consistent view of the whole product from a
camera ELEV degrees above it (orthographic, like a long studio lens):

  * label and base: the photographed pixels, re-projected column by column. The tube is a
    cylinder, so each column keeps its angle on the tube; only its vertical position
    changes with the viewpoint. The local viewing angle of the packshot is measured from
    printed straight lines (logo baseline, divider line, label edge). No printed detail
    is created, removed or moved along the label.
  * cap, collar ring, neck, rim and inside wall: solids of revolution, ray-cast from the
    profile measured on the packshot's silhouette and shaded with the white-plastic light
    measured on the collar ring of the packshot (so they match the photographed parts).
  * the 15 small bridges in the cap's groove are its only non-round detail; they are
    what makes the rotation visible. benefit-cap.webp holds CAP_FRAMES frames of the cap
    turned by one bridge spacing / CAP_FRAMES each; the pattern repeats every bridge, so
    CSS can show any rotation with these few frames.
  * the tablet: the same ray-marched tablet as the rest of the site (render_product.py),
    re-rendered for this camera, lying flat in frame 0 and at its resting angle in the
    last frame.

Outputs (assets/images/), all registered in one stage of STAGE_W x STAGE_H px:
  benefit-tube.webp        tube with collar ring, threaded neck and the FRONT half of the rim
                           (the opening is transparent, so the tablet can sit inside)
  benefit-tube-inner.webp  the BACK half of the rim and the inside wall seen through the opening
  benefit-cap.webp         CAP_FRAMES frames of the cap, stacked vertically
  benefit-tablet.webp      TABLET_FRAMES frames of the tablet, side by side
  tools/benefits-layers.json   placement of every layer in % of the stage, plus the motion
                               numbers used by css/benefits.css
"""
import json
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_product as rp  # noqa: E402
import build_hero_layers as bh  # noqa: E402

ROOT, OUT = rp.ROOT, rp.OUT

# ---- camera ---------------------------------------------------------------------------
ELEV = 14.0                      # degrees above the product
SE, CE = math.sin(math.radians(ELEV)), math.cos(math.radians(ELEV))
SS = 4                           # supersampling

# ---- product profile, in source px (h = row of the packshot at the tube's silhouette) -----
R_BODY = 162.94                  # label body (measured)
H_TOP, R_CAP, FIL_TOP = 97.5, 179.5, 6.0          # cap: top plane, wall radius, rounded top edge
CAP_LINES = (120.5, 134.5)       # two shallow grooves round the cap wall (silhouette dips)
H_WALL_END, R_RECESS, H_CAP_BOT = 152.5, 175.3, 160.0   # recessed groove with the bridges
BRIDGES, BRIDGE_PHI0, BRIDGE_W, R_BRIDGE = 15, -73.6, 3.0, 177.6   # measured: every 24 deg
R_BAND, H_BAND_FIL, H_LABEL = 176.7, 208.0, 217.0  # collar ring (stays on the tube), label top
H_BASE, FIL_BASE = 1426.43, 5.0  # contact line, rounded bottom edge (render_product.tube_alpha)
# neck under the cap (never photographed: sized to fit inside the cap)
H_RIM, R_NECK, R_INNER = 106.0, 164.0, 157.5
PITCH, THREAD_H = 26.0, 5.0      # right-hand thread
THREAD_A, THREAD_TURN = -165.0, 525.0  # start angle and length of the thread (deg)
# measured local viewing angle of the printed label (deg; negative = seen from below)
LABEL_ELEV = [(97, -8.3), (156.5, -6.88), (217, -5.8), (283, -1.7), (1226.5, 4.08),
              (1403.3, 6.32), (1426.4, 8.27), (1470, 8.27)]

# ---- stage and motion -------------------------------------------------------------------
STAGE_W, X_AX = 384, 192.0       # stage width, tube axis column
Y_OFF = 356.0                    # y = Y_OFF + h*cos(e) + z*sin(e)
CAP_LIFT = 384.0                 # final cap lift (source px; the cap ends ~3 cm above the rim)
CAP_TILT = -6.0                  # final in-plane tilt of the lifted cap (deg)
CAP_SHIFT = 6.0                  # final sideways drift of the lifted cap (px)
CAP_FRAMES = 6                   # frames per bridge spacing
SPIN = 312.0                     # total cap rotation (deg), a multiple of the bridge spacing
SPIN_ENGAGED = 216.0             # rotation while the thread still carries the cap
TABLET_R = 146.0                 # tablet radius (0.93 x the inner radius of the neck)
TABLET_FRAMES, TABLET_PX = 16, 320
TABLET_TILT, TABLET_ROLL = 42.0, -10.0   # resting angle in the last frame (camera tilt, roll)
TABLET_DEPTH0 = 82.0             # start: tablet top face this far below the rim (hidden)
TABLET_REST_H = -23.0            # final tablet centre (h); tablet hovers between rim and cap


def proj_y(h, z):
    return Y_OFF + h * CE + z * SE


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# =========================================================================================
# light: white plastic shading measured on the collar ring of the packshot
# =========================================================================================
class Light:
    def __init__(self, a, x0):
        e_band = math.radians(-6.88)
        Xs = np.arange(-R_BAND + 1.5, R_BAND - 1.5, 0.5)
        z = np.sqrt(np.clip(R_BAND ** 2 - Xs ** 2, 0, None))
        rows = [182 + o + z * math.sin(e_band) for o in range(-9, 10, 3)]
        smp = [cv2.remap(a, (x0 + Xs).astype(np.float32).reshape(1, -1), r.astype(np.float32).reshape(1, -1),
                         cv2.INTER_LINEAR).reshape(-1, 3) for r in rows]
        S = np.median(np.stack(smp), axis=0)
        phi = np.arcsin(np.clip(Xs / R_BAND, -1, 1))
        ok = np.abs(phi) < math.radians(80)
        phi, S = phi[ok], S[ok]
        # extend to +-90 deg with the trend of the last 10 deg
        for side in (-1, 1):
            sel = (side * phi) > math.radians(70)
            k = np.polyfit(phi[sel], S[sel], 1)
            ext = np.linspace(side * math.radians(80.5), side * math.radians(90), 12)
            ev = np.stack([np.polyval(k[:, c], ext) for c in range(3)], -1)
            phi = np.concatenate([phi, ext]) if side > 0 else np.concatenate([ext, phi])
            S = np.concatenate([S, ev]) if side > 0 else np.concatenate([ev, S])
        o = np.argsort(phi)
        self.phi = phi[o]
        self.S = np.stack([cv2.GaussianBlur(S[o][:, c].reshape(-1, 1).astype(np.float32), (1, 0),
                                            sigmaX=1, sigmaY=3).ravel() for c in range(3)], -1)
        self.top = np.clip(self.S.max(0) * 1.012, 0, 0.985)   # surfaces facing up: the top softbox
        print("  light: side", np.round(self.S[len(self.S) // 2], 3), "top", np.round(self.top, 3))

    def side(self, phi):
        phi = np.clip(phi, self.phi[0], self.phi[-1])
        return np.stack([np.interp(phi, self.phi, self.S[:, c]) for c in range(3)], -1)

    def shade(self, nx, ny, nz):
        """nx, ny, nz: unit normal (x right, y up, z towards the camera)."""
        phi = np.arctan2(nx, np.maximum(nz, -0.2))
        s = self.side(phi)
        up = np.clip(ny, 0, 1)[..., None]
        dn = np.clip(-ny, 0, 1)[..., None]
        return s * (1 - up - dn) + self.top * up + s * 0.5 * dn


# =========================================================================================
# column renderer: surfaces of revolution seen from above, one column at a time
# =========================================================================================
def resolve(yo, valid, rows):
    """First path sample (in path order) that covers each output row.
    yo: [ncol, n] projected y of the path, valid: [ncol, n].
    Returns idx [ncol, nrow] (or -1) of the sample seen at each row."""
    y = np.where(valid, yo, -np.inf)
    run = np.maximum.accumulate(y, axis=1)
    ncol, n = y.shape
    idx = np.empty((ncol, len(rows)), np.int64)
    for c in range(ncol):
        idx[c] = np.searchsorted(run[c], rows, side="left")
    last = np.where(np.isfinite(run[:, -1]), run[:, -1], -np.inf)
    first_valid = np.where(valid.any(1), np.argmax(valid, 1), n)
    first_y = y[np.arange(ncol), np.minimum(first_valid, n - 1)]
    cover = (rows[None, :] <= last[:, None]) & (rows[None, :] >= first_y[:, None]) & (idx < n)
    return np.where(cover, np.minimum(idx, n - 1), -1)


def gather(arr, idx):
    """arr [ncol, n, ...] indexed by idx [ncol, nrow] -> [nrow, ncol, ...] (image layout)."""
    c = np.arange(arr.shape[0])[:, None]
    out = arr[c, np.maximum(idx, 0)]
    return np.swapaxes(out, 0, 1)


def downsample(rgb, cov):
    """SS -> 1x with premultiplied area averaging."""
    h, w = cov.shape[0] // SS, cov.shape[1] // SS
    pm = cv2.resize((rgb * cov[..., None]).astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
    a = cv2.resize(cov.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
    return rp.unpremul(pm, a), np.clip(a, 0, 1)


def columns(x0_px, x1_px):
    """Stage x range (px) -> SS column centres as offsets X from the tube axis."""
    xs = (np.arange((x1_px - x0_px) * SS) + 0.5) / SS + x0_px
    return xs - X_AX


def rows_of(y0_px, y1_px):
    return (np.arange((y1_px - y0_px) * SS) + 0.5) / SS + y0_px


def profile_path(X, segs):
    """Front (z >= 0) path over a list of profile segments. Each seg: dict with arrays
    h, r (radius), nr, ny (2-D normal: radial, up) sampled along the profile, plus tags.
    Returns per-column arrays [ncol, n]."""
    h = np.concatenate([s["h"] for s in segs])
    r = np.concatenate([s["r"] for s in segs])
    nr = np.concatenate([s["nr"] for s in segs])
    ny = np.concatenate([s["ny"] for s in segs])
    tag = np.concatenate([np.full(len(s["h"]), s["tag"], np.int16) for s in segs])
    Xc = X[:, None]
    z = np.sqrt(np.clip(r[None, :] ** 2 - Xc ** 2, 0, None))
    valid = r[None, :] > np.abs(Xc)
    rr = np.maximum(r[None, :], 1e-3)
    nx3 = nr[None, :] * Xc / rr
    nz3 = nr[None, :] * z / rr
    ny3 = np.broadcast_to(ny[None, :], z.shape)
    H = np.broadcast_to(h[None, :], z.shape)
    T = np.broadcast_to(tag[None, :], z.shape)
    R = np.broadcast_to(r[None, :], z.shape)
    return dict(h=H, z=z, r=R, nx=nx3, ny=ny3, nz=nz3, tag=T, valid=valid, yo=proj_y(H, z))


def seg_line(h0, h1, r0, r1, tag, step=0.05):
    n = max(2, int(abs(h1 - h0) / step) + 1, int(abs(r1 - r0) / step) + 1)
    t = np.linspace(0, 1, n)
    h = h0 + (h1 - h0) * t
    r = r0 + (r1 - r0) * t
    dh, dr = h1 - h0, r1 - r0
    L = math.hypot(dh, dr) or 1
    # outward normal of a profile running downwards/outwards: (radial, up) = (dh, dr)/L
    return dict(h=h, r=r, nr=np.full(n, dh / L), ny=np.full(n, dr / L), tag=tag)


def seg_arc(hc, rc, rad_h, rad_r, a0, a1, tag, step=0.05):
    """Elliptic arc of the profile; angle 90 = straight up, 0 = radial out (deg)."""
    n = max(8, int(abs(a1 - a0) / 180 * math.pi * max(rad_h, rad_r) / step))
    a = np.radians(np.linspace(a0, a1, n))
    r = rc + rad_r * np.cos(a)
    h = hc - rad_h * np.sin(a)
    gx, gy = np.cos(a) / max(rad_r, 1e-6), np.sin(a) / max(rad_h, 1e-6)
    L = np.hypot(gx, gy)
    return dict(h=h, r=r, nr=gx / L, ny=gy / L, tag=tag)


# =========================================================================================
# the cap (one frame per rotation step)
# =========================================================================================
def cap_bridge_mask(phi_deg, turn):
    """1 on a bridge (soft edges) for the cap turned by `turn` degrees (front moves right)."""
    p = 360.0 / BRIDGES
    d = np.mod(phi_deg - BRIDGE_PHI0 - turn + p / 2, p) - p / 2
    return np.clip((BRIDGE_W / 2 - np.abs(d)) / 0.5 + 0.5, 0, 1)


def render_cap(light, turn):
    x0, x1 = int(X_AX - R_CAP - 4), int(X_AX + R_CAP + 5)
    y0 = int(proj_y(H_TOP, -R_CAP) - 3)
    y1 = int(proj_y(H_CAP_BOT, R_CAP) + 3)
    X = columns(x0, x1)
    rows = rows_of(y0, y1)
    ncol = len(X)

    # 1) top face, back to front (only where |X| < radius of the flat top)
    r_flat = R_CAP - FIL_TOP
    zt = np.sqrt(np.clip(r_flat ** 2 - X ** 2, 0, None))
    nt = 700
    s = np.linspace(-1, 1, nt)[None, :]
    z_top = zt[:, None] * s
    top = dict(h=np.full((ncol, nt), H_TOP), z=z_top, valid=np.broadcast_to(zt[:, None] > 0, (ncol, nt)),
               nx=np.zeros((ncol, nt)), ny=np.ones((ncol, nt)), nz=np.zeros((ncol, nt)),
               tag=np.full((ncol, nt), 1, np.int16), r=np.sqrt(X[:, None] ** 2 + z_top ** 2))
    top["yo"] = proj_y(top["h"], top["z"])

    # 2) front profile: rounded top edge, wall with two grooves, recess with bridges
    segs = [seg_arc(H_TOP + FIL_TOP, r_flat, FIL_TOP, FIL_TOP, 90, 0, 2)]
    hs = np.arange(H_TOP + FIL_TOP, H_WALL_END, 0.04)
    dip = np.zeros_like(hs)
    for c in CAP_LINES:
        dip += 1.1 * np.exp(-((hs - c) / 1.3) ** 2)
    rw = R_CAP - dip
    drdh = np.gradient(rw, hs)
    L = np.hypot(1, drdh)
    segs.append(dict(h=hs, r=rw, nr=1 / L, ny=drdh / L, tag=3))       # (dh, dr) = (1, dr/dh)
    segs.append(seg_arc(H_WALL_END, R_CAP - 1.6, 1.5, 1.6, 0, -90, 4))  # rounded lower edge of the wall
    segs.append(seg_line(H_WALL_END + 1.5, H_WALL_END + 1.5, R_CAP - 1.6, R_RECESS, 4))
    segs.append(seg_line(H_WALL_END + 1.5, H_CAP_BOT, R_RECESS, R_RECESS, 5))
    P = profile_path(X, segs)

    path = {k: np.concatenate([top[k], P[k]], axis=1) for k in ("h", "z", "r", "nx", "ny", "nz", "tag", "valid", "yo")}
    # bridges: the recess (tag 5) bulges out to R_BRIDGE on each bridge
    rec = path["tag"] == 5
    phi = np.degrees(np.arcsin(np.clip(X[:, None] / R_RECESS, -1, 1)))
    br = cap_bridge_mask(np.broadcast_to(phi, rec.shape), turn) * rec
    r_b = np.where(rec, R_RECESS + (R_BRIDGE - R_RECESS) * br, path["r"])
    z_b = np.sqrt(np.clip(r_b ** 2 - X[:, None] ** 2, 0, None))
    path["z"] = np.where(rec, z_b, path["z"])
    path["valid"] = path["valid"] | (rec & (r_b > np.abs(X[:, None])))
    path["yo"] = proj_y(path["h"], path["z"])

    idx = resolve(path["yo"], path["valid"], rows)
    g = {k: gather(path[k], idx) for k in ("h", "z", "nx", "ny", "nz", "tag")}
    bridge = gather(br, idx)
    cov = (idx >= 0).T.astype(np.float32)
    col = light.shade(g["nx"], g["ny"], g["nz"])

    # top face: soft gradient (brighter towards the back), slight fall-off at the very edge
    t1 = g["tag"] == 1
    back = np.clip(-g["z"] / R_CAP, -1, 1)
    col = np.where(t1[..., None], col * (0.985 + 0.02 * back[..., None]), col)
    # wall grooves: a little ambient occlusion in each groove
    ao = np.ones_like(g["h"])
    for c in CAP_LINES:
        ao -= 0.07 * np.exp(-((g["h"] - c) / 1.0) ** 2)
    # recess: deep shadow under the overhanging wall, lighter towards its bottom; bridges catch light
    t5 = (g["tag"] == 5) | (g["tag"] == 4)
    depth = np.clip((g["h"] - (H_WALL_END + 1.5)) / (H_CAP_BOT - H_WALL_END - 1.5), 0, 1)
    rec_ao = 0.46 + 0.20 * depth
    br_ao = 0.84 + 0.06 * depth
    ao = np.where(t5, rec_ao * (1 - bridge) + br_ao * bridge, ao)
    col = col * ao[..., None]
    # bridge sides: darker where the bridge turns away from the light
    side_dark = 1 - 0.18 * np.clip(bridge * (1 - bridge) * 4, 0, 1)
    col = np.where(t5[..., None], col * side_dark[..., None], col)
    rgb, a = downsample(col, cov)
    return rgb, a, (x0, y0)


# =========================================================================================
# the tube: neck + front rim + collar ring (rendered), label + base (photographed)
# =========================================================================================
def thread_height(h, phi_deg):
    """Radial height of the neck thread at (h, phi), and the shadow it casts on the wall
    just below it (the studio light comes from above). Right-hand thread: rises to the right."""
    out = np.zeros_like(h)
    shadow = np.zeros_like(h)
    for n in (0, 1, -1):
        psi = phi_deg + 360.0 * n
        on = (psi >= THREAD_A) & (psi <= THREAD_A + THREAD_TURN)
        hc = 152.0 - PITCH * (psi - THREAD_A) / 360.0
        d = h - hc
        prof = np.clip((5.0 - np.abs(d)) / 3.2, 0, 1)
        prof = prof * prof * (3 - 2 * prof)
        taper = smooth(THREAD_A, THREAD_A + 28, psi) * (1 - smooth(THREAD_A + THREAD_TURN - 28, THREAD_A + THREAD_TURN, psi))
        out = np.maximum(out, THREAD_H * prof * taper * on)
        sh = np.clip(1 - np.abs(d - 6.6) / 3.0, 0, 1) * taper * on
        shadow = np.maximum(shadow, sh)
    return out, shadow


def label_elev(h):
    k = np.array(LABEL_ELEV)
    return np.sin(np.radians(np.interp(h, k[:, 0], k[:, 1])))


def render_tube(light, src_rgb, x_src0, seam):
    x0, x1 = int(X_AX - R_BAND - 4), int(X_AX + R_BAND + 5)
    y0 = int(proj_y(H_RIM, -R_NECK) - 3)
    y1 = int(proj_y(H_BASE, R_BODY) + 4)
    X = columns(x0, x1)
    rows = rows_of(y0, y1)
    ncol = len(X)

    # front half of the rim (flat top with rounded edges): from the inner edge (or the
    # silhouette) to the outer edge
    rim_w = R_NECK - R_INNER
    zi = np.sqrt(np.clip(R_INNER ** 2 - X ** 2, 0, None))
    zo = np.sqrt(np.clip(R_NECK ** 2 - X ** 2, 0, None))
    nt = 90
    sz = np.linspace(0, 1, nt)[None, :]
    z_rim = zi[:, None] + (zo - zi)[:, None] * sz
    r_rim = np.sqrt(X[:, None] ** 2 + z_rim ** 2)
    u = np.clip((r_rim - R_INNER) / rim_w, 0, 1)      # 0 inner edge .. 1 outer edge
    lip = np.clip(np.minimum(u, 1 - u) / 0.28, 0, 1)  # rounded edges: normal tips in/out
    tilt = (1 - lip) * np.where(u < 0.5, -1, 1) * 0.75
    ny_r = np.sqrt(np.clip(1 - tilt ** 2, 0, 1))
    rim = dict(h=np.full((ncol, nt), H_RIM) + (1 - lip) * 0.6, z=z_rim,
               valid=np.broadcast_to((zo > 0)[:, None], (ncol, nt)),
               nx=tilt * X[:, None] / np.maximum(r_rim, 1e-3), ny=ny_r, nz=tilt * z_rim / np.maximum(r_rim, 1e-3),
               tag=np.full((ncol, nt), 10, np.int16), r=r_rim)
    rim["yo"] = proj_y(rim["h"], rim["z"])

    # neck wall (with thread), collar ring, band, its rounded lower edge
    hs = np.arange(H_RIM + 0.6, H_CAP_BOT, 0.04)
    segs = [dict(h=hs, r=np.full_like(hs, R_NECK), nr=np.ones_like(hs), ny=np.zeros_like(hs), tag=11)]
    segs.append(seg_line(H_CAP_BOT, H_CAP_BOT, R_NECK, R_BAND - 1.4, 12))           # ledge (faces up)
    segs.append(seg_arc(H_CAP_BOT + 1.4, R_BAND - 1.4, 1.4, 1.4, 90, 0, 12))
    segs.append(seg_line(H_CAP_BOT + 1.4, H_BAND_FIL, R_BAND, R_BAND, 13, step=0.1))
    segs.append(seg_arc(H_BAND_FIL, R_BODY, H_LABEL - H_BAND_FIL, R_BAND - R_BODY, 0, -90, 13))
    P = profile_path(X, segs)
    # thread: displace the neck wall radially
    t11 = P["tag"] == 11
    phi_n = np.degrees(np.arcsin(np.clip(X[:, None] / R_NECK, -1, 1)))
    th, th_sh = thread_height(P["h"], np.broadcast_to(phi_n, P["h"].shape))
    th, th_sh = th * t11, th_sh * t11
    dth = np.gradient(th, axis=1) / 0.04
    r_t = P["r"] + th
    z_t = np.sqrt(np.clip(r_t ** 2 - X[:, None] ** 2, 0, None))
    Lt = np.hypot(1, dth)
    nr_t = np.where(t11, 1 / Lt, 1.0)
    ny_t = np.where(t11, dth / Lt, P["ny"])
    P["z"] = np.where(t11, z_t, P["z"])
    P["valid"] = np.where(t11, r_t > np.abs(X[:, None]), P["valid"])
    P["nx"] = np.where(t11, nr_t * X[:, None] / np.maximum(r_t, 1e-3), P["nx"])
    P["nz"] = np.where(t11, nr_t * z_t / np.maximum(r_t, 1e-3), P["nz"])
    P["ny"] = ny_t
    P["yo"] = proj_y(P["h"], P["z"])
    P["th"], P["sh"] = th, th_sh

    rim["th"] = np.zeros_like(rim["h"])
    rim["sh"] = np.zeros_like(rim["h"])
    keys = ("h", "z", "nx", "ny", "nz", "tag", "valid", "yo", "th", "sh")
    path = {k: np.concatenate([rim[k], P[k]], axis=1) for k in keys}
    idx = resolve(path["yo"], path["valid"], rows)
    g = {k: gather(path[k], idx) for k in ("h", "z", "nx", "ny", "nz", "tag", "th", "sh")}
    cov = (idx >= 0).T.astype(np.float32)
    col = light.shade(g["nx"], g["ny"], g["nz"])
    # ambient occlusion: under each thread turn, at the foot of the neck, on the ledge next to it
    ao = np.ones(g["h"].shape, np.float32)
    t11 = g["tag"] == 11
    ao -= t11 * 0.22 * smooth(H_CAP_BOT - 7, H_CAP_BOT, g["h"])
    ao -= t11 * 0.05                                                 # the neck sits in the collar's light shadow
    ao -= t11 * 0.26 * g["sh"] * (g["th"] < 0.5)                    # shadow under each thread turn
    ao -= t11 * 0.16 * (g["ny"] < -0.05)                             # underside of the thread
    crest = t11 * np.clip(g["th"] / THREAD_H - 0.7, 0, 1) / 0.3 * (g["ny"] > -0.2)
    ao += 0.08 * crest                                               # crest catches the top light
    t12 = g["tag"] == 12
    rr_l = np.sqrt(np.broadcast_to(X[None, :], g["z"].shape) ** 2 + g["z"] ** 2)
    ao -= t12 * 0.25 * np.exp(-np.clip(rr_l - R_NECK, 0, None) / 2.5)
    col = col * ao[..., None]
    rgb_top = col

    # label + base: photographed pixels, re-projected. Visible below the band's lowest edge.
    last_band = np.where(path["valid"], path["yo"], -np.inf).max(1)
    zb = np.sqrt(np.clip(R_BODY ** 2 - X ** 2, 0, None))
    Y = rows[:, None]
    h_body = (Y - Y_OFF - zb[None, :] * SE) / CE
    vis_body = (Y > last_band[None, :]) & (np.abs(X)[None, :] < R_BODY) & (h_body >= H_LABEL)
    # bottom outline: the contact circle rounded by FIL_BASE (analytic, sub-pixel by SS)
    edge = R_BODY - np.abs(X)
    lift = np.where(edge < FIL_BASE, FIL_BASE - np.sqrt(np.clip(FIL_BASE ** 2 - (FIL_BASE - edge) ** 2, 0, None)), 0)
    vis_body &= h_body <= (H_BASE - lift)[None, :]
    zz = np.broadcast_to(zb[None, :], h_body.shape)
    ys = h_body + zz * label_elev(h_body)
    xs_src = np.broadcast_to((x_src0 + X)[None, :], h_body.shape)
    seam_at = np.interp(xs_src, np.arange(len(seam)) + 0.5, seam)
    ys = np.maximum(ys, seam_at + 1.2)                  # never sample the cap/label seam line
    body = cv2.remap(src_rgb.astype(np.float32), (xs_src - 0.5).astype(np.float32), (ys - 0.5).astype(np.float32),
                     cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    body = np.clip(body, 0, 1)
    col = np.where(vis_body[..., None], body, rgb_top)
    cov = np.maximum(cov, vis_body.astype(np.float32))
    rgb, a = downsample(col, cov)
    return rgb, a, (x0, y0)


# =========================================================================================
# inside of the tube: back half of the rim + inner wall, seen through the opening
# =========================================================================================
def render_inner(light):
    x0, x1 = int(X_AX - R_NECK - 3), int(X_AX + R_NECK + 4)
    y0 = int(proj_y(H_RIM, -R_NECK) - 3)
    y1 = int(proj_y(H_RIM + 2 * R_INNER * SE / CE + 6, -R_INNER) + 4)
    X = columns(x0, x1)
    rows = rows_of(y0, y1)
    ncol = len(X)
    rim_w = R_NECK - R_INNER
    zi = np.sqrt(np.clip(R_INNER ** 2 - X ** 2, 0, None))
    zo = np.sqrt(np.clip(R_NECK ** 2 - X ** 2, 0, None))
    nt = 90
    sz = np.linspace(0, 1, nt)[None, :]
    z_end = np.where(zi > 0, -zi, np.minimum(zo, 2.5))   # beyond the hole: overlap the front half
    z_rim = -zo[:, None] + (z_end + zo)[:, None] * sz     # back outer edge -> back inner edge
    r_rim = np.sqrt(X[:, None] ** 2 + z_rim ** 2)
    u = np.clip((r_rim - R_INNER) / rim_w, 0, 1)
    lip = np.clip(np.minimum(u, 1 - u) / 0.28, 0, 1)
    tilt = (1 - lip) * np.where(u < 0.5, -1, 1) * 0.75
    rim = dict(h=np.full((ncol, nt), H_RIM) + (1 - lip) * 0.6, z=z_rim, valid=np.broadcast_to((zo > 0)[:, None], (ncol, nt)),
               nx=tilt * X[:, None] / np.maximum(r_rim, 1e-3), ny=np.sqrt(np.clip(1 - tilt ** 2, 0, 1)),
               nz=tilt * z_rim / np.maximum(r_rim, 1e-3), tag=np.full((ncol, nt), 20, np.int16))
    rim["yo"] = proj_y(rim["h"], rim["z"])
    nw = 1400
    depth = np.linspace(0.6, 2 * R_INNER * SE / CE + 6, nw)[None, :]
    wall = dict(h=H_RIM + np.broadcast_to(depth, (ncol, nw)), z=np.broadcast_to(-zi[:, None], (ncol, nw)),
                valid=np.broadcast_to((zi > 0)[:, None], (ncol, nw)),
                nx=np.broadcast_to(-X[:, None] / R_INNER, (ncol, nw)), ny=np.zeros((ncol, nw)),
                nz=np.broadcast_to(zi[:, None] / R_INNER, (ncol, nw)), tag=np.full((ncol, nw), 21, np.int16))
    wall["yo"] = proj_y(wall["h"], wall["z"])
    path = {k: np.concatenate([rim[k], wall[k]], axis=1) for k in ("h", "z", "nx", "ny", "nz", "tag", "valid", "yo")}
    idx = resolve(path["yo"], path["valid"], rows)
    g = {k: gather(path[k], idx) for k in ("h", "z", "nx", "ny", "nz", "tag")}
    cov = (idx >= 0).T.astype(np.float32)
    col = light.shade(g["nx"], g["ny"], g["nz"])
    # inside: lit through the opening only, so it darkens quickly with depth (and towards the
    # sides, where the wall turns away); a soft contact line just under the far rim
    d = np.clip(g["h"] - H_RIM, 0, None)
    Xi = np.broadcast_to(X[None, :], d.shape)
    side = 1 - 0.30 * (Xi / R_INNER) ** 2
    lum = (0.15 + 0.74 * np.exp(-d / 24.0)) * side * (1 - 0.22 * np.exp(-(d / 1.6) ** 2))
    inner_col = np.stack([lum * 0.985, lum * 0.975, lum * 0.97], -1) * light.top
    col = np.where((g["tag"] == 21)[..., None], inner_col, col)
    rgb, a = downsample(col, cov)
    return rgb, a, (x0, y0)


# =========================================================================================
def crop_save(name, rgb, a, origin, quality=92):
    ys, xs = np.where(a > 0.003)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = np.dstack([np.clip(rgb[y0:y1, x0:x1], 0, 1), a[y0:y1, x0:x1]])
    img = Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA")
    path = os.path.join(OUT, name)
    img.save(path, "WEBP", quality=quality, method=6, alpha_quality=100)
    print(f"  wrote assets/images/{name}  {img.size[0]}x{img.size[1]}  {os.path.getsize(path) // 1024} KB")
    return dict(x=origin[0] + int(x0), y=origin[1] + int(y0), w=int(x1 - x0), h=int(y1 - y0)), img


def main():
    a = np.asarray(Image.open(rp.DEFAULT_SRC).convert("RGB")).astype(np.float32) / 255.0
    geo, d, obj = rp.measure(a)
    alpha = rp.tube_alpha(a, geo, d, obj)
    rgb = rp.decontaminate(a, alpha, np.array(geo["bg"], np.float32))
    seam = bh.seam_rows(a, geo)
    light = Light(a, geo["x0"])
    x_src0 = geo["x0"]

    place = {}
    print("  tube ...")
    t_rgb, t_a, t_o = render_tube(light, rgb, x_src0, seam)
    place["tube"], _ = crop_save("benefit-tube.webp", t_rgb, t_a, t_o)
    print("  inside ...")
    i_rgb, i_a, i_o = render_inner(light)
    place["inner"], _ = crop_save("benefit-tube-inner.webp", i_rgb, i_a, i_o)

    print("  cap frames ...")
    step = 360.0 / BRIDGES / CAP_FRAMES
    frames = []
    for k in range(CAP_FRAMES):
        c_rgb, c_a, c_o = render_cap(light, k * step)
        frames.append((c_rgb, c_a))
    # one common box for all frames
    A = np.max([f[1] for f in frames], axis=0)
    ys, xs = np.where(A > 0.003)
    by0, by1, bx0, bx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    strip = np.concatenate([np.dstack([np.clip(f[0][by0:by1, bx0:bx1], 0, 1), f[1][by0:by1, bx0:bx1]]) for f in frames], 0)
    img = Image.fromarray((strip * 255 + 0.5).astype(np.uint8), "RGBA")
    img.save(os.path.join(OUT, "benefit-cap.webp"), "WEBP", quality=92, method=6, alpha_quality=100)
    print(f"  wrote assets/images/benefit-cap.webp  {img.size[0]}x{img.size[1]}  "
          f"{os.path.getsize(os.path.join(OUT, 'benefit-cap.webp')) // 1024} KB")
    place["cap"] = dict(x=c_o[0] + int(bx0), y=c_o[1] + int(by0), w=int(bx1 - bx0), h=int(by1 - by0))

    if "--fast" not in sys.argv:
        print("  tablet strip ...")
        bh.FRAMES, bh.FRAME_PX = TABLET_FRAMES, TABLET_PX
        bh.render_strip("benefit-tablet.webp", seed=7, spin=20, tilt0=ELEV, tilt1=TABLET_TILT, roll1=TABLET_ROLL)

    # ---- geometry for the CSS --------------------------------------------------------
    span = 1.32                                   # render_tablet frame half-width in tablet radii
    stage_h = int(math.ceil(proj_y(H_BASE, R_BODY) + 52))
    g = dict(
        elev=ELEV, stage=[STAGE_W, stage_h], axis_x=X_AX,
        tube=place["tube"], inner=place["inner"], cap=place["cap"],
        cap_frames=CAP_FRAMES, bridge_deg=360.0 / BRIDGES, spin=SPIN, spin_engaged=SPIN_ENGAGED, pitch=PITCH,
        cap_lift_px=CAP_LIFT * CE, cap_tilt=CAP_TILT, cap_shift=CAP_SHIFT,
        tablet=dict(size=2 * span * TABLET_R, frames=TABLET_FRAMES, rest_y=proj_y(TABLET_REST_H, 0)),
        rim_y=proj_y(H_RIM, 0), base_y=proj_y(H_BASE, 0), base_front_y=proj_y(H_BASE, R_BODY),
        body_w=2 * R_BODY,
    )
    path = os.path.join(ROOT, "tools", "benefits-layers.json")
    with open(path, "w") as f:
        json.dump(g, f, indent=2)
    print("  geometry:", json.dumps(g))
    write_css(g)


# =========================================================================================
# motion: one timeline, written into css/benefits.css between the @generated markers
# =========================================================================================
T_CAP0, T_CAP = 0.10, 1.40       # cap: unscrews (thread engaged), then lifts free and tilts
T_TAB0, T_TAB = 1.06, 0.84       # tablet: rises from inside the tube to its hovering position
T_FACTS0, FACT_STEP = 1.46, 0.09  # benefits 01..06, as the tablet settles
FLOAT_PERIOD = 5.2
CAP_FPS, SPIN_FPS = 30, 60       # keyframe sampling (spin: one key per display frame)
RIM_CLEAR, CAP_CLEAR = 4.0, 12.0  # px the tablet keeps above the rim / below the cap (3-D)


def ease_sine(u):
    return 0.5 - 0.5 * math.cos(math.pi * u)


def ease_cubic(u):
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def cap_state(u):
    """Cap at time fraction u of its window: rotation, lift (h px), in-plane tilt, sideways shift.
    While the thread is engaged the cap rises by one pitch per turn; after that it lifts
    free (Hermite curve that starts with the screw's own speed) and tips slightly."""
    th = SPIN * ease_sine(u)
    u_d = math.acos(1 - 2 * SPIN_ENGAGED / SPIN) / math.pi
    l_d = PITCH * SPIN_ENGAGED / 360
    if u <= u_d:
        return th, PITCH * th / 360, 0.0, 0.0
    s = (u - u_d) / (1 - u_d)
    m0 = PITCH / 360 * SPIN * math.pi / 2 * math.sin(math.pi * u_d) * (1 - u_d)
    lift = (2 * s ** 3 - 3 * s ** 2 + 1) * l_d + (s ** 3 - 2 * s ** 2 + s) * m0 + (-2 * s ** 3 + 3 * s ** 2) * CAP_LIFT
    e = ease_sine(s)
    return th, lift, CAP_TILT * e, CAP_SHIFT * e


def tablet_tilt(frame):
    e = frame / (TABLET_FRAMES - 1)
    e = e * e * (3 - 2 * e)                       # same easing as build_hero_layers.render_strip
    return TABLET_TILT * e + ELEV * (1 - e) - ELEV   # world tilt (deg)


def tablet_extent(frame):
    """Vertical half-extent of the tablet (h px) at a frame: radius * sin(tilt) + half thickness."""
    t = math.radians(tablet_tilt(frame))
    return TABLET_R * math.sin(t) + 0.24 * TABLET_R * math.cos(t)


def write_css(g):
    W, H = g["stage"]
    half_t = 0.24 * TABLET_R
    start_h = H_RIM + TABLET_DEPTH0 + half_t
    rest_h = TABLET_REST_H

    def tab_h(t):
        u = min(max((t - T_TAB0) / T_TAB, 0), 1)
        return start_h + (rest_h - start_h) * ease_cubic(u)

    # the tablet stays flat (it is inside the tube) until its bottom clears the rim; from then
    # on it turns towards its resting angle, never dipping back below the rim
    ts = np.arange(T_TAB0, T_TAB0 + T_TAB + 1e-9, 0.002)
    t_clear = next(t for t in ts if tab_h(t) + half_t <= H_RIM - RIM_CLEAR)
    t_end = T_TAB0 + T_TAB
    for _ in range(200):
        ok = all(tab_h(t) + tablet_extent((TABLET_FRAMES - 1) * (t - t_clear) / (t_end - t_clear)) <= H_RIM - RIM_CLEAR
                 for t in ts if t >= t_clear)
        if ok:
            break
        t_clear += 0.005
    # the lifting cap must stay above the rising tablet
    worst = 1e9
    for t in ts:
        u = min(max((t - T_CAP0) / T_CAP, 0), 1)
        _, lift, tilt, _ = cap_state(u)
        f = 0 if t < t_clear else (TABLET_FRAMES - 1) * (t - t_clear) / (t_end - t_clear)
        cap_low = H_CAP_BOT - lift + R_CAP * math.sin(math.radians(abs(tilt)))
        worst = min(worst, (tab_h(t) - tablet_extent(f)) - cap_low)
    assert worst >= CAP_CLEAR, f"cap and tablet come within {worst:.1f}px"
    print(f"  motion: tablet clears the rim at {t_clear:.2f}s, closest cap-tablet gap {worst:.1f}px")

    pc = lambda v: f"{v:.4g}"                                 # noqa: E731
    cqw = lambda px: f"{px / W * 100:.3f}cqw"                 # noqa: E731
    cqh = lambda px: f"{px / H * 100:.3f}cqh"                 # noqa: E731
    box = lambda b: (f"left: {b['x'] / W * 100:.3f}%; top: {b['y'] / H * 100:.3f}%; "   # noqa: E731
                     f"width: {b['w'] / W * 100:.3f}%; height: {b['h'] / H * 100:.3f}%;")

    _, lift1, tilt1, shift1 = cap_state(1.0)
    tab = g["tablet"]
    tb = dict(x=X_AX - tab["size"] / 2, y=tab["rest_y"] - tab["size"] / 2, w=tab["size"], h=tab["size"])
    shadow_w = 1.62 * R_BODY * 2
    shadow_h = shadow_w * 182 / 628
    sb = dict(x=X_AX - shadow_w / 2, y=g["base_y"] - shadow_h * 0.52, w=shadow_w, h=shadow_h)

    L = []
    L.append("/* @generated:begin by tools/build_benefits_layers.py -- do not edit by hand */")
    L.append(f".bx {{ aspect-ratio: {W} / {H}; }}")
    L.append(f".bx__inner {{ {box(g['inner'])} }}")
    L.append(f".bx__tube {{ {box(g['tube'])} }}")
    L.append(f".bx__shadow {{ {box(sb)} }}")
    L.append(f".bx__tab {{ {box(tb)} }}")
    L.append(f".bx__cap {{ {box(g['cap'])} translate: {cqw(shift1)} {cqh(-lift1 * CE)}; rotate: {pc(tilt1)}deg; }}")
    L.append(f".bx__cap-strip {{ height: {CAP_FRAMES * 100}%; }}")
    L.append(f".bx__tab-strip {{ width: {TABLET_FRAMES * 100}%; translate: {-(TABLET_FRAMES - 1) / TABLET_FRAMES * 100:.4f}% 0; }}")
    L.append(".benefits {")
    L.append(f"  --bx-cap-delay: {T_CAP0}s; --bx-cap-dur: {T_CAP}s;")
    L.append(f"  --bx-tab-delay: {T_TAB0}s; --bx-tab-dur: {T_TAB}s;")
    L.append(f"  --bx-turn-delay: {t_clear:.3f}s; --bx-turn-dur: {t_end - t_clear:.3f}s;")
    L.append(f"  --bx-facts-delay: {T_FACTS0}s; --bx-facts-step: {FACT_STEP}s;")
    L.append(f"  --bx-float-delay: {t_end:.2f}s; --bx-float-dur: {FLOAT_PERIOD}s;")
    L.append("}")

    # cap: lift + tilt (linear between keys sampled from the eased curve)
    n = int(round(T_CAP * CAP_FPS))
    keys = []
    for i in range(n + 1):
        u = i / n
        _, lift, tilt, shift = cap_state(u)
        keys.append(f"{u * 100:.2f}% {{ translate: {cqw(shift)} {cqh(-lift * CE)}; rotate: {pc(tilt)}deg; }}")
    L.append("@keyframes bx-cap {")
    L += ["  " + k for k in keys]
    L.append("}")

    # spin: which of the CAP_FRAMES frames shows, one key per display frame (step-end)
    n = int(round(T_CAP * SPIN_FPS))
    step = 360.0 / BRIDGES / CAP_FRAMES
    last, keys = None, []
    for i in range(n + 1):
        u = i / n
        th, *_ = cap_state(u)
        k = int(math.floor(th / step + 1e-6)) % CAP_FRAMES
        if k != last:
            keys.append(f"{u * 100:.2f}%{{translate:0 {-k / CAP_FRAMES * 100:.4f}%}}")
            last = k
    L.append("@keyframes bx-spin {")
    for i in range(0, len(keys), 4):
        L.append("  " + " ".join(keys[i:i + 4]))
    L.append("}")

    # tablet: rise (sampled), then the frame strip turns it once it is out of the tube
    n = int(round(T_TAB * CAP_FPS))
    keys = []
    for i in range(n + 1):
        u = i / n
        dy = proj_y(tab_h(T_TAB0 + u * T_TAB), 0) - tab["rest_y"]
        keys.append(f"{u * 100:.2f}% {{ translate: 0 {cqh(dy)}; }}")
    L.append("@keyframes bx-tab {")
    L += ["  " + k for k in keys]
    L.append("}")
    L.append("@keyframes bx-tab-turn { from { translate: 0 0; } }")
    L.append("/* @generated:end */")

    css_path = os.path.join(ROOT, "css", "benefits.css")
    css = open(css_path, encoding="utf-8").read()
    a = css.find("/* @generated:begin")
    b = css.find("/* @generated:end */")
    assert a >= 0 and b > a, "css/benefits.css needs the @generated markers"
    css = css[:a] + "\n".join(L) + css[b + len("/* @generated:end */"):]
    with open(css_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(css)
    print(f"  updated css/benefits.css ({len(L)} generated lines)")


if __name__ == "__main__":
    if "--css" in sys.argv:          # timings only: reuse the rendered layers
        with open(os.path.join(ROOT, "tools", "benefits-layers.json")) as f:
            write_css(json.load(f))
    else:
        main()

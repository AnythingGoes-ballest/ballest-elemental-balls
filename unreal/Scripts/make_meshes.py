"""Generates the Elemental Balls v2 geometry (procedural, deterministic, reviewable): Python 3 + numpy.

  python make_meshes.py

Now only Frost's glass shell (the look is the concept pictures projected onto the plugin's sphere.glb; the earlier
procedural meshes, slate plates, obsidian fragments and ice shards, are in git history, commit 59191e0).
Writes models/v2_<part>.glb (the game plugin's mesh: metres, glTF axes) and SourceArt/<part>.obj (centimetres, for the
editor previews). Every mesh carries zero-area triangles at +-50 cm on each axis, so all parts share one bounding box
centred on the ball: a model file places each with `at=0,0,-50` (a mesh stands on the bottom of its bounds).
"""
import json
import math
import os
import struct

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", ".."))
MODELS = os.path.join(PLUGIN, "models")
OBJDIR = os.path.normpath(os.path.join(HERE, "..", "SourceArt"))


class Mesh:
    def __init__(self):
        self.p, self.n, self.uv = [], [], []

    def smooth_tri(self, a, b, c, na, nb, nc, uv=((0, 0), (1, 0), (0, 1))):
        self.p += [np.asarray(a, float), np.asarray(b, float), np.asarray(c, float)]
        self.n += [np.asarray(na, float), np.asarray(nb, float), np.asarray(nc, float)]
        self.uv += list(uv)

    def arrays(self):
        p = np.array(self.p, float).reshape(-1, 3)
        n = np.array(self.n, float).reshape(-1, 3)
        uv = np.array(self.uv, float).reshape(-1, 2)
        mk = np.vstack([np.eye(3), -np.eye(3)]) * 50.0          # shared bounds: zero-area triangles at +-50 cm
        p = np.vstack([p, np.repeat(mk, 3, 0)])
        n = np.vstack([n, np.tile([0, 0, 1.0], (18, 1))])
        uv = np.vstack([uv, np.zeros((18, 2))])
        return p, n, uv


def gl(v):
    """Ball space (z up; game x forward, y right) to glTF (y up): the host maps glTF (x, y, z) to the game's
    (z, -x, y), so ball (X, Y, Z) is glTF (-Y, Z, X). (From make_assets.py, measured.)"""
    v = np.asarray(v, np.float64)
    return np.stack([-v[..., 1], v[..., 2], v[..., 0]], -1)


def write_glb(path, mesh):
    p, n, uv = mesh.arrays()
    gp, gn = gl(p) / 100.0, gl(n)
    idx = np.arange(len(gp), dtype=np.uint32).reshape(-1, 3)
    for k, (a, b, c) in enumerate(idx):              # counter-clockwise seen from the normal, in glTF's axes
        if np.cross(gp[b] - gp[a], gp[c] - gp[a]) @ gn[a] < 0:
            idx[k] = (a, c, b)
    blobs = [gp.astype(np.float32).tobytes(), gn.astype(np.float32).tobytes(), uv.astype(np.float32).tobytes(),
             idx.astype(np.uint32).tobytes()]
    views, at = [], 0
    for blob, target in zip(blobs, (34962, 34962, 34962, 34963)):
        views.append({"buffer": 0, "byteOffset": at, "byteLength": len(blob), "target": target})
        at += (len(blob) + 3) // 4 * 4
    nv = len(gp)
    gltf = {"asset": {"version": "2.0", "generator": "Elemental Balls make_meshes.py"},
            "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "indices": 3}]}],
            "buffers": [{"byteLength": at}], "bufferViews": views,
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": nv, "type": "VEC3",
                 "min": gp.min(0).tolist(), "max": gp.max(0).tolist()},
                {"bufferView": 1, "componentType": 5126, "count": nv, "type": "VEC3"},
                {"bufferView": 2, "componentType": 5126, "count": nv, "type": "VEC2"},
                {"bufferView": 3, "componentType": 5125, "count": idx.size, "type": "SCALAR"}]}
    binary = b"".join(b + b"\0" * ((len(b) + 3) // 4 * 4 - len(b)) for b in blobs)
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((len(js) + 3) // 4 * 4 - len(js))
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binary))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(binary), 0x004E4942) + binary
    with open(path, "wb") as f:
        f.write(out)


def write_obj(path, mesh):
    """For the editor previews. Measured: UE's OBJ import maps (x, y, z) to (x, -y, z), so write mirrored."""
    p, n, uv = mesh.arrays()
    p = p * [1, -1, 1]
    n = n * [1, -1, 1]
    with open(path, "w") as f:
        for v in p:
            f.write("v %.4f %.4f %.4f\n" % tuple(v))
        for v in n:
            f.write("vn %.5f %.5f %.5f\n" % tuple(v))
        for v in uv:
            f.write("vt %.5f %.5f\n" % (v[0], v[1]))
        for k in range(0, len(p), 3):           # counter-clockwise seen from the normal, in the file's own axes
            a, b, c = k + 1, k + 2, k + 3
            if np.cross(p[k + 1] - p[k], p[k + 2] - p[k]) @ n[k] < 0:
                b, c = c, b
            f.write("f %d/%d/%d %d/%d/%d %d/%d/%d\n" % (a, a, a, b, b, b, c, c, c))


def save(name, mesh):
    os.makedirs(MODELS, exist_ok=True)
    os.makedirs(OBJDIR, exist_ok=True)
    write_glb(os.path.join(MODELS, "v2_%s.glb" % name), mesh)
    write_obj(os.path.join(OBJDIR, "%s.obj" % name), mesh)
    print("%-13s %6d triangles" % (name, len(mesh.p) // 3))


def sphere_mesh(radius, around=96, rings=48):
    m = Mesh()
    for j in range(rings):
        t0, t1 = math.pi * j / rings, math.pi * (j + 1) / rings
        for i in range(around):
            p0, p1 = 2 * math.pi * i / around, 2 * math.pi * (i + 1) / around
            q = [np.array([math.sin(t) * math.cos(p), math.sin(t) * math.sin(p), math.cos(t)])
                 for t, p in ((t0, p0), (t0, p1), (t1, p0), (t1, p1))]
            for a, b, c in ((0, 2, 1), (1, 2, 3)):
                if min(np.linalg.norm(q[a] - q[b]), np.linalg.norm(q[b] - q[c]), np.linalg.norm(q[a] - q[c])) < 1e-9:
                    continue
                m.smooth_tri(q[a] * radius, q[b] * radius, q[c] * radius, q[a], q[b], q[c])
    return m


def main():
    save("frost_shell", sphere_mesh(49.3))


if __name__ == "__main__":
    main()

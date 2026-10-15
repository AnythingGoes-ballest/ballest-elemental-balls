"""Makes the tileable 3D noise volumes the Elemental Balls v2 materials sample (procedural, no outside images).

Writes 512x512 PNG atlases (8x8 tiles of 64x64 = a 64^3 volume, slice z = row*8 + col) into ../SourceArt/.
build_materials.py imports them as Texture2D and turns them into VolumeTextures.

T_EB_Noise  (RGBA): R = band-limited noise (about 4 cycles per tile), G/B/A = three independent smoother
                     noises (about 3 cycles) used as a domain-warp / flow vector.
T_EB_Cells  (RGBA): periodic Worley cells, 5x5x5 jittered points: R = F1 distance, G = F2 - F1 (0 on a cell
                     border, so a thin bright line is 1 - smoothstep), B = random per-cell value, A = second
                     random per-cell value.
All volumes tile, so the shader can sample octaves at 2x, 4x the coordinates.

Run with any Python 3 that has numpy and Pillow:  python make_noise.py
"""
import os
import numpy as np
from PIL import Image

N = 64
TILES = 8
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SourceArt")


def band_noise(rng, f0, width):
    """Tileable noise whose spectrum is a Gaussian ring around f0 cycles per tile, normalised to 0..1."""
    white = rng.standard_normal((N, N, N))
    F = np.fft.fftn(white)
    k = np.fft.fftfreq(N) * N
    kx, ky, kz = np.meshgrid(k, k, k, indexing="ij")
    r = np.sqrt(kx * kx + ky * ky + kz * kz)
    filt = np.exp(-((r - f0) ** 2) / (2 * width * width))
    filt[0, 0, 0] = 0
    v = np.real(np.fft.ifftn(F * filt))
    v = v / (np.std(v) * 2 * 2.6) + 0.5          # +-2.6 sigma -> 0..1
    return np.clip(v, 0, 1)


def worley(rng, cells):
    pts = (np.stack(np.meshgrid(*[np.arange(cells)] * 3, indexing="ij"), -1) + rng.random((cells, cells, cells, 3))) / cells
    ids_a = rng.random((cells, cells, cells))
    ids_b = rng.random((cells, cells, cells))
    g = (np.arange(N) + 0.5) / N
    X, Y, Z = np.meshgrid(g, g, g, indexing="ij")
    P = np.stack([X, Y, Z], -1)
    f1 = np.full((N, N, N), 9.0)
    f2 = np.full((N, N, N), 9.0)
    ida = np.zeros((N, N, N))
    idb = np.zeros((N, N, N))
    for i in range(cells):
        for j in range(cells):
            for l in range(cells):
                d = P - pts[i, j, l]
                d -= np.round(d)                      # periodic
                dist = np.sqrt((d * d).sum(-1))
                closer = dist < f1
                f2 = np.where(closer, f1, np.minimum(f2, dist))
                ida = np.where(closer, ids_a[i, j, l], ida)
                idb = np.where(closer, ids_b[i, j, l], idb)
                f1 = np.where(closer, dist, f1)
    scale = cells                                     # distances in cell units
    return np.clip(f1 * scale, 0, 1), np.clip((f2 - f1) * scale, 0, 1), ida, idb


def atlas(chans):
    vol = np.stack(chans, -1)                         # N,N,N,4 indexed x,y,z
    img = np.zeros((N * TILES, N * TILES, 4))
    for z in range(N):
        r, c = divmod(z, TILES)
        img[r * N:(r + 1) * N, c * N:(c + 1) * N] = vol[:, :, z].transpose(1, 0, 2)   # rows = y, cols = x
    return Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGBA")


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(20261014)
    noise = [band_noise(rng, 4.0, 1.2), band_noise(rng, 3.0, 1.0), band_noise(rng, 3.0, 1.0), band_noise(rng, 3.0, 1.0)]
    atlas(noise).save(os.path.join(OUT, "T_EB_Noise_Atlas.png"))
    atlas(list(worley(rng, 5))).save(os.path.join(OUT, "T_EB_Cells_Atlas.png"))
    print("wrote", OUT)


if __name__ == "__main__":
    main()

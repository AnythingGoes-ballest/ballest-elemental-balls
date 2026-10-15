"""The three balls as parts: one table used by build_materials.py (the instances), render_previews.py (the preview
assembly) and write_models.py (the plugin's model files), so the editor and the game always show the same thing.

The look is the concept pictures projected onto the ball (project_concepts.py's maps, drawn by M_EB_Ball). The
earlier procedural look (geometry + six procedural styles) is retired; it's in git history (commit 59191e0).

Each part: (mesh, instance name, master, parameter overrides). Meshes: "ball" = the plugin's 1 m sphere.glb at the
ball's size, "aura" = the same sphere at AuraScale, others = make_meshes.py's models/v2_<mesh>.glb.
Masters: "ball" = M_EB_Ball (opaque, lit, clear coat), "glow" = M_EB_Glow (additive; Mode 0 aura, 1 glass shell).
String values are textures of ours (asset names under /Game/Mods/elemental_balls).
"""

AURA_SCALE = 1.35


def _ball(B, **tune):
    # Customize: picture front to the camera (FaceCam), visible flow (~0.15 rad/s), a light clear coat (a crisp
    # highlight and rim without a horizon band across the middle)
    ov = {"Radius": 49.0, "Emis": 1.0, "SheenAmt": 1.0, "SpecAmt": 0.2, "CoatAmt": 0.15, "CoatRough": 0.03,
          "FaceCam": 1.0, "FlowAmt": 0.6, "FlowRate": 0.25,
          "GrazeCut": 0.1, "ProjBase": "T_Proj_%s_Base" % B, "ProjEmis": "T_Proj_%s_Emis" % B,
          "ProjNorm": "T_Proj_%s_Norm" % B}
    ov.update(tune)
    return ("ball", "MI_EB_%s" % B, "ball", ov)


def _aura(B, **ov):
    base = {"Mode": 0, "ShellRadius": 66.15, "AuraStrength": 0.5}
    base.update(ov)
    return ("aura", "MI_EB_Aura_%s" % B, "glow", base)


PARTS = {
    # BakeAmt: how much of the picture's painted shading of the outer layer shows as-is, on top of game lighting
    "Void": [_ball("Void", BakeAmt=3.5, DetailAmt=1.0, SparkleAmt=1.0),
             _aura("Void", Twist=0.9, SparkAmt=1.3, C1=(0.55, 0.08, 1.0), C2=(0.05, 0.6, 1.0), C3=(0.75, 0.6, 1.0))],
    "Frost": [_ball("Frost", BakeAmt=0.3, Emis=0.85, DetailAmt=0.8, SparkleAmt=1.4),
              ("frost_shell", "MI_EB_FrostGlass", "glow", {"Mode": 1, "ShellRadius": 49.3, "RimAmt": 1.0, "MilkAmt": 0.15,
                                                          "AuraEmis": 1.0, "C2": (0.6, 0.82, 1.0)}),
              _aura("Frost", Twist=0.3, Falloff=5.0, SparkAmt=1.4, Speed=0.5, Flicker=0.05,
                    C1=(0.15, 0.5, 1.0), C2=(0.35, 0.75, 1.0), C3=(0.9, 0.97, 1.0))],
    "Toxic": [_ball("Toxic", BakeAmt=0.8, Emis=2.0, DetailAmt=0.8, SparkleAmt=0.6),
              _aura("Toxic", Twist=0.5, SparkAmt=0.8, Rise=0.45,
                    C1=(0.3, 1.0, 0.04), C2=(0.0, 0.85, 0.6), C3=(0.6, 1.0, 0.2))],
}
ALL = PARTS

# races are in daylight: the race ball gets these multipliers of its `set` values (model files). Reflections off
# (measured in game: any clear coat or specular mirrors the yellow start pad as a band); GrazeCut x10 = 1:
# reflections fade out toward the silhouette (the yellow start pad reflected along the lower edge).
RACE = {"ball": {"Emis": 2.0, "CoatAmt": 0.0, "SpecAmt": 0.0, "GrazeCut": 10.0, "FaceCam": 0.0}, "glow": {"AuraStrength": 2.0}}

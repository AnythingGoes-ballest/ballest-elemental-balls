"""Rebuilds the Elemental Balls v2 cooked content from the text sources, in one go:

  1. make_noise.py          -> SourceArt/*.png (tileable noise volumes, procedural)
  2. make_meshes.py         -> models/v2_*.glb (the game's meshes) + SourceArt/*.obj (previews) + the river table
  2b. project_concepts.py  -> SourceArt/proj_*.png (approach B: the concept pictures projected onto the ball)
  3. write_models.py        -> models/v2_<ball>.txt (from balls.py)
  4. build_materials.py     -> the content project's assets, node by node, inside UE 5.8 (headless)
  5. make_mod_container.py  -> <plugin>/assets/elemental_balls_b<N>-Windows.utoc/.ucas/.pak (cook + IoStore package)

  python rebuild_all.py [--clean] [--assets <dir>] [--no-container] [--tool <make_mod_container.py>]

--clean deletes the content project's generated folders first (Content, Saved, Intermediate, DerivedDataCache), so the
result comes only from the scripts. --assets defaults to the plugin's own assets/ folder (use a slot's plugin folder
to hot-reload into a running test copy). The .uasset/.utoc/.ucas/.pak files are build output: never commit them.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.normpath(os.path.join(HERE, ".."))
PLUGIN = os.path.normpath(os.path.join(PROJ_DIR, ".."))
UPROJECT = os.path.join(PROJ_DIR, "elemental_balls.uproject")
ENGINE = r"C:\Program Files\Epic Games\UE_5.8"
DEFAULT_TOOL = os.path.normpath(os.path.join(PLUGIN, "..", "pm-assets", "tools", "make_mod_container.py"))


def step(label, cmd, **kw):
    t = time.time()
    print("==", label)
    p = subprocess.run(cmd, **kw)
    if p.returncode != 0:
        sys.exit("%s failed (%d)" % (label, p.returncode))
    print("   %.1f s" % (time.time() - t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--assets", default=os.path.join(PLUGIN, "assets"))
    ap.add_argument("--no-container", action="store_true")
    ap.add_argument("--tool", default=DEFAULT_TOOL)
    a = ap.parse_args()

    if a.clean:
        for d in ["Content", "Saved", "Intermediate", "DerivedDataCache"]:
            shutil.rmtree(os.path.join(PROJ_DIR, d), ignore_errors=True)
        print("== cleaned the content project")
    step("noise volumes", [sys.executable, os.path.join(HERE, "make_noise.py")])
    step("meshes", [sys.executable, os.path.join(HERE, "make_meshes.py")])
    step("concept projections", [sys.executable, os.path.join(HERE, "project_concepts.py")])
    step("model files", [sys.executable, os.path.join(HERE, "write_models.py")])
    log = os.path.join(PROJ_DIR, "Saved", "build_materials.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    step("materials (UE 5.8, headless)",
         [os.path.join(ENGINE, r"Engine\Binaries\Win64\UnrealEditor-Cmd.exe"), UPROJECT, "-run=pythonscript",
          "-script=" + os.path.join(HERE, "build_materials.py").replace("\\", "/"), "-AllowCommandletRendering",
          "-unattended", "-nop4", "-nosplash", "-abslog=" + log],
         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(log, encoding="utf-8", errors="replace") as fo:
        lines = fo.read().splitlines()
    for line in lines:
        if "[EB]" in line:
            print("  ", line.split("[EB]", 1)[1].strip())
    if any("Python script executed with errors" in line or ": error:" in line for line in lines):
        sys.exit("build_materials.py reported errors: see " + log)
    if not a.no_container:
        step("container", [sys.executable, a.tool, UPROJECT, a.assets], cwd=os.path.dirname(os.path.dirname(a.tool)))


if __name__ == "__main__":
    main()

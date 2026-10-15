# Elemental Balls

A cosmetic plugin for the [Ballest plugin manager](https://github.com/AnythingGoes-ballest/ballest-plugin-manager): three
glowing balls for Ballest of Them All, painted from Aarib's concept art.

- **Void Crystal**: obsidian plates with violet, magenta and cyan crystal glowing between them.
- **Frost**: white ice round a deep blue core, inside a glass shell.
- **Toxic Current**: lime and teal liquid glowing inside black glass.

Each ball's glowing layer sits deeper than its surface and drifts slowly under a clear coat, with a soft aura around
the ball. In Customize the picture's front turns to face the camera; in races the coat is turned down so the ball stays
readable.

Needs plugin manager host **0.27.0** or newer, and the **Cosmetic Kit** plugin (installed with it).

## How they're made

These balls use real materials with their own shaders. The plugin manager loads them from a cooked container that comes
with the plugin (`assets/`, host 0.27.0's plugin content support). Everything in it is built from the text sources in
`unreal/Scripts/`:

1. `project_concepts.py` maps each concept picture onto the ball (base colour, normals and the glowing layer).
   The concept pictures themselves are not in this repo: a rebuild needs them in `unreal/concepts/` (gitignored).
2. `build_materials.py` builds the two master materials (`M_EB_Ball`: lit with a clear coat, the glowing layer drawn
   deeper and drifting along a flow map; `M_EB_Glow`: the aura and Frost's glass shell) and the balls' instances,
   node by node, in Unreal Engine 5.8.3.
3. `make_meshes.py` makes Frost's glass shell (`models/v2_frost_shell.glb`), and `write_models.py` writes the model files
   (`models/v2_<ball>.txt`).
4. `rebuild_all.py --clean` does all of it and packages the container with the plugin manager's
   `tools/make_mod_container.py`.

The container is build output: it is never committed. The maintainers build it from these scripts and attach it to the
plugin's GitHub release, and the plugin manager downloads it from there and checks its SHA-256. It only contains
materials and textures under `/Game/Mods/elemental_balls/`, and the plugin manager refuses anything else.

## Install

In the game: **plugins** > **browse** > **Elemental Balls** > **install**. Then pick a ball on the Customize page, in
the plugin's own section.

## Credits

See [CREDITS.txt](CREDITS.txt).

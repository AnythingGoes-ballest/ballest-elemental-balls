"""Renders preview frames of the Elemental Balls v2 (all parts of each ball, from balls.PARTS), headless:

  UnrealEditor.exe <proj> -RenderOffscreen -unattended -nop4 -nosplash
      -ExecutePythonScript="<this file> <outdir> [balls] [times] [scenes] [aura] [grid:<name>]"

(the full editor ticking offscreen; a commandlet's scene captures came back black). Quits the editor when done.
scenes: concept  front view on a dark backdrop, the ball filling the frame like the concept art (fidelity check)
        customize  grey studio like the game's Customize page (exposure matched to in-game shots)
        race     sunny-ish: yellow start pad, blue surroundings, the ball at chase-camera size (~28% of a 16:9 frame)
aura:   "noaura", "aura" (strength from the instance), or a comma list of AuraStrength values (suffix _a<value>)
Time comes from each material's TimeOffset, so frames are exact. Writes <outdir>/<ball>_<scene>_t<sec>[...].png (2x
supersampled; compose_sheets.py downsizes).
"""
import math
import os
import sys
import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import balls  # noqa: E402

EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
ACT = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
BASE = "/Game/Mods/elemental_balls"

args = sys.argv[1:]
OUT = args[0] if args else os.path.join(os.environ["TEMP"], "eb_previews")
BALLS = args[1].split(",") if len(args) > 1 else ["Void", "Frost", "Toxic"]
TIMES = [float(x) for x in args[2].split(",")] if len(args) > 2 else [0.0, 1.0, 2.0]
SCENES = args[3].split(",") if len(args) > 3 else ["concept", "customize", "race"]
AURA_ARG = args[4] if len(args) > 4 else "aura"
AURAS = [] if AURA_ARG == "noaura" else [None] if AURA_ARG == "aura" else [float(v) for v in AURA_ARG.split(",")]
GRID = None
if len(args) > 5 and args[5].startswith("grid:"):     # variant grids: a variants.py with GRIDS = {name: {ball: [(label, {param: value})]}}
    import variants
    GRID = variants.GRIDS[args[5][5:]]
os.makedirs(OUT, exist_ok=True)


def log(*a):
    unreal.log_warning("[EBR] " + " ".join(str(x) for x in a))


def color_material(name, rgb, rough=0.6, emissive=0.0):
    path = "/Game/Preview/" + name
    if EAL.does_asset_exist(path):
        m = EAL.load_asset(path)
        MEL.delete_all_material_expressions(m)
    else:
        m = AT.create_asset(name, "/Game/Preview", unreal.Material, unreal.MaterialFactoryNew())
    c = MEL.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -300, 0)
    c.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1))
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    r = MEL.create_material_expression(m, unreal.MaterialExpressionConstant, -300, 200)
    r.set_editor_property("r", rough)
    MEL.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    if emissive > 0:
        e = MEL.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -300, 300)
        e.set_editor_property("constant", unreal.LinearColor(rgb[0] * emissive, rgb[1] * emissive, rgb[2] * emissive, 1))
        MEL.connect_material_property(e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    return m


def spawn(cls, loc=(0, 0, 0), rot=(0, 0, 0)):
    return ACT.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(*rot))


def mesh(path, loc, scale, mat, rot=(0, 0, 0)):
    a = spawn(unreal.StaticMeshActor, loc, rot)
    c = a.static_mesh_component
    c.set_static_mesh(unreal.load_object(None, path))
    a.set_actor_scale3d(unreal.Vector(*scale))
    if mat:
        c.set_material(0, mat)
    return a


def look_rot(cam, target):
    d = [target[i] - cam[i] for i in range(3)]
    yaw = math.degrees(math.atan2(d[1], d[0]))
    pitch = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    return unreal.Rotator(roll=0, pitch=pitch, yaw=yaw)


def build_scene(kind):
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sky_src, cube = "captured", None
    if kind == "concept":
        dark = color_material("M_PV_Backdrop", (0.004, 0.005, 0.012), 0.9)
        mesh("/Engine/BasicShapes/Plane.Plane", (900, 0, 0), (60, 60, 1), dark, (0, 90, 0))
        mesh("/Engine/BasicShapes/Plane.Plane", (0, 0, -55), (60, 60, 1), dark)
        soft = color_material("M_PV_Softbox", (1, 1, 1), 1.0, emissive=3.0)
        mesh("/Engine/BasicShapes/Plane.Plane", (-150, -200, 230), (2.5, 4, 1), soft, (0, 0, 120))   # softboxes: seen
        mesh("/Engine/BasicShapes/Plane.Plane", (-120, 240, 160), (1.5, 3, 1), soft, (0, 0, 60))     # only in reflections
        mesh("/Engine/BasicShapes/Plane.Plane", (-60, 0, -200), (3, 3, 1), soft, (0, 0, 180))
        key = spawn(unreal.DirectionalLight, (0, 0, 500), (-40, -35, 0))
        key.light_component.set_intensity(2.5)
        sky_int = 0.15
    elif kind == "customize":
        grey = color_material("M_PV_Grey", (0.16, 0.16, 0.17), 0.8, emissive=0.5)
        darkm = color_material("M_PV_Dark", (0.02, 0.02, 0.02), 0.3)
        gold = color_material("M_PV_Gold", (0.9, 0.55, 0.05), 0.35)
        mesh("/Engine/BasicShapes/Plane.Plane", (600, 0, 0), (40, 40, 1), grey, (0, 90, 0))
        mesh("/Engine/BasicShapes/Cylinder.Cylinder", (0, 0, -95), (2.6, 2.6, 0.9), darkm)
        mesh("/Engine/BasicShapes/Cylinder.Cylinder", (0, 0, -52), (2.75, 2.75, 0.04), gold)
        soft = color_material("M_PV_Softbox", (1, 1, 1), 1.0, emissive=4.0)
        mesh("/Engine/BasicShapes/Plane.Plane", (-150, -260, 260), (2.5, 4, 1), soft, (0, 0, 120))
        mesh("/Engine/BasicShapes/Plane.Plane", (-200, 300, 120), (1.5, 3, 1), soft, (0, 0, 70))
        sun = spawn(unreal.DirectionalLight, (0, 0, 500), (-35, -150, 0))
        sun.light_component.set_intensity(1.2)
        fill = spawn(unreal.PointLight, (-250, 250, 150))
        fill.point_light_component.set_intensity(12)
        fill.point_light_component.set_attenuation_radius(1500)
        sky_int = 0.25
    else:
        yellow = color_material("M_PV_Yellow", (0.85, 0.62, 0.02), 0.5)
        water = color_material("M_PV_Water", (0.05, 0.25, 0.42), 0.15)
        skyc = color_material("M_PV_Sky", (0.35, 0.55, 0.8), 1.0, emissive=0.9)
        blue = color_material("M_PV_Blue", (0.05, 0.2, 0.5), 0.4)
        mesh("/Engine/BasicShapes/Plane.Plane", (0, 0, -150), (200, 200, 1), water)
        mesh("/Engine/BasicShapes/Cylinder.Cylinder", (0, 0, -100), (5.5, 5.5, 1.0), yellow)
        mesh("/Engine/BasicShapes/Cube.Cube", (900, 0, 0), (4, 6, 2.5), blue)
        mesh("/Engine/BasicShapes/Plane.Plane", (6000, 0, 1500), (200, 200, 1), skyc, (0, 90, 0))
        sun = spawn(unreal.DirectionalLight, (0, 0, 500), (-50, 30, 0))
        sun.light_component.set_intensity(2.6)
        sky_src, cube = "cube", "/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap"
        sky_int = 0.5
    sky = spawn(unreal.SkyLight)
    sc = sky.light_component
    if sky_src == "captured":
        sc.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_CAPTURED_SCENE)
    else:
        sc.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
        sc.set_cubemap(unreal.load_object(None, cube))
    sc.set_intensity(sky_int)
    sc.recapture_sky()
    return world


def assemble(ball, rot):
    """All of a ball's parts at the origin, each with its own MID (returned for TimeOffset / variants)."""
    actors, mids = [], []
    for m, mi_name, master, _ in balls.ALL[ball]:
        if m == "ball":
            a = mesh("/Game/Preview/SM_PreviewBall.SM_PreviewBall", (0, 0, 0), (0.98,) * 3, None, rot)
        elif m == "aura":
            if not AURAS:
                continue
            a = mesh("/Game/Preview/SM_PreviewBall.SM_PreviewBall", (0, 0, 0), (balls.AURA_SCALE,) * 3, None)
        else:
            a = mesh("/Game/Preview/SM_%s.SM_%s" % (m, m), (0, 0, 0), (1, 1, 1), None, rot)
        a.static_mesh_component.set_cast_shadow(master == "ball")
        mi = unreal.load_object(None, "%s/%s.%s" % (BASE, mi_name, mi_name))
        mid = a.static_mesh_component.create_dynamic_material_instance(0, mi)
        if m == "aura":
            mid.set_scalar_parameter_value("ShellRadius", 50.0)      # the radius-50 preview sphere, scaled
        actors.append(a)
        mids.append((m, master, mid))
    return actors, mids


def make_capture(world, kind):
    if kind == "concept":
        w, h, fov = 1024, 1024, 30.0
        d = 50.0 / (math.tan(math.radians(15)) * 0.86)
        cam = (-d, 0, 0)
    elif kind == "customize":
        w, h, fov, cam = 1024, 1024, 50.0, (-230 * math.cos(math.radians(8)), 0, 230 * math.sin(math.radians(8)))
    else:
        w, h, fov = 1280, 720, 90.0
        d = 317.0
        cam = (-d * math.cos(math.radians(16)), 0, d * math.sin(math.radians(16)))
    ss = 2
    rt = unreal.RenderingLibrary.create_render_target2d(world, w * ss, h * ss, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    capa = spawn(unreal.SceneCapture2D, cam)
    capa.set_actor_rotation(look_rot(cam, (0, 0, 0)), False)
    cc = capa.capture_component2d
    cc.set_editor_property("fov_angle", fov)
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    cc.set_editor_property("capture_every_frame", False)
    cc.set_editor_property("capture_on_movement", False)
    pps = cc.get_editor_property("post_process_settings")
    if kind in ("customize", "concept"):   # the game's Customize page measured ~1.7x brighter than this rig
        pps.set_editor_property("override_auto_exposure_bias", True)
        pps.set_editor_property("auto_exposure_bias", 0.75)
    pps.set_editor_property("override_motion_blur_amount", True)
    pps.set_editor_property("motion_blur_amount", 0.0)
    cc.set_editor_property("post_process_settings", pps)
    return cc, rt


def shoot(world, cc, rt, name, label=None):
    for _ in range(3):
        cc.capture_scene()
        yield 2
    unreal.RenderingLibrary.export_render_target(world, rt, OUT, name)
    if label:
        with open(os.path.join(OUT, name[:-4] + ".txt"), "w") as fo:
            fo.write(label)
    log("wrote", name, label or "")


def steps():
    """Generator: each yield = wait that many editor ticks."""
    for kind in SCENES:
        world = build_scene(kind)
        cc, rt = make_capture(world, kind)
        yield 60
        for b in BALLS:
            rot = (0, 0, 0) if kind == "concept" else (20, 35, 10)
            actors, mids = assemble(b, rot)
            yield 240 if b == BALLS[0] else 90           # shaders and meshes in
            sets = GRID.get(b, []) if GRID is not None else [(None, {})]
            for t in TIMES:
                for vi, (vlabel, vparams) in enumerate(sets):
                    for m, master, mid in mids:
                        mid.set_scalar_parameter_value("TimeOffset", t)
                    for k, v in vparams.items():           # "part:Param" targets one part, "Param" every part
                        part, _, pname = k.rpartition(":")
                        for m, master, mid in mids:
                            if not part or part == m:
                                mid.set_scalar_parameter_value(pname, float(v))
                    for a in (AURAS or [None]):
                        if a is not None:
                            for m, master, mid in mids:
                                if m == "aura":
                                    mid.set_scalar_parameter_value("AuraStrength", a)
                        yield 3
                        suffix = ("_v%d" % vi if GRID is not None else "") + \
                                 ("_a%g" % a if a is not None and len(AURAS) > 1 else "")
                        yield from shoot(world, cc, rt, "%s_%s_t%g%s.png" % (b.lower(), kind, t, suffix), vlabel)
            for a in actors:
                ACT.destroy_actor(a)
            yield 5
    log("DONE")


GEN = steps()
STATE = {"wait": 300, "handle": None}     # first wait: let editor startup shader compiles finish


def tick(dt):
    if STATE.get("busy"):                 # new_blank_map etc. tick Slate inside a step: don't re-enter
        return
    if STATE["wait"] > 0:
        STATE["wait"] -= 1
        return
    try:
        STATE["busy"] = True
        STATE["wait"] = next(GEN)
        STATE["busy"] = False
    except StopIteration:
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
        unreal.SystemLibrary.quit_editor()
    except Exception as e:
        log("ERROR", repr(e))
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
        unreal.SystemLibrary.quit_editor()


unreal.EditorPythonScripting.set_keep_python_script_alive(True)   # else -ExecutePythonScript quits after this file
STATE["handle"] = unreal.register_slate_post_tick_callback(tick)

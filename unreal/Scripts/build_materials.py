"""Builds the Elemental Balls v2 assets in the elemental_balls UE 5.8 content project (plugin elemental-balls). Run:

  UnrealEditor-Cmd.exe <proj>/elemental_balls.uproject -run=pythonscript -script=<this file> -AllowCommandletRendering
      -unattended -nop4 -nosplash

(rebuild_all.py runs make_noise.py and make_meshes.py first, then this, then the container.) Rebuilds every graph from
the HLSL in hlsl/ each run. Shipped content (under /Game/Mods/elemental_balls/, the host's container gate):
  VT_EB_Noise, VT_EB_Cells   64^3 tileable noise / Worley-cell volumes (RGBA8, procedural, inline mips)
  M_EB_Ball                  ONE opaque lit master (Clear Coat via Make Material Attributes, world-space normal):
                             Style 0 Void crystal, 1 Frost vortex backdrop, 2 Toxic liquid, 3 slate, 4 glowing seam,
                             5 obsidian, chosen by a uniform [branch]
  M_EB_Glow                  ONE additive unlit master (translucent after DOF): Mode 0 aura, 1 ice shards, 2 glass
  MI_EB_*                    the parts' instances, from balls.PARTS
Editor only (never cooked): /Game/SourceArt (volume sources), /Game/Preview (meshes for previews, preview materials).
Every look decision is a parameter: variants and in-game `set` lines need no recompile.
"""
import math
import os
import sys
import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import balls  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
HLSL = os.path.join(HERE, "hlsl")
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
BASE = "/Game/Mods/elemental_balls"

# The look is the concept pictures projected onto the ball (Style 0 = hlsl/projected.hlsl). The procedural styles of
# the earlier approach are retired (git history, commit 59191e0).
BALL_SCALARS = [("Style", 0.0), ("Speed", 1.0), ("Emis", 1.0), ("Radius", 49.0), ("SheenAmt", 1.0), ("ProjDepth", 0.08),
                ("FlowAmt", 0.15), ("BakeAmt", 0.0), ("DetailAmt", 1.0), ("SparkleAmt", 1.0), ("GrazeCut", 0.1),
                ("FlowRate", 0.08), ("FaceCam", 0.0)]
BALL_VECTORS = []
BALL_STYLES = ["projected"]                                                                     # Style 0
BALL_TEX2D = ["ProjBase", "ProjEmis", "ProjNorm"]                 # Style 6's concept-projected maps
GLOW_SCALARS = [("Mode", 0.0), ("ShellRadius", 66.15), ("Speed", 1.0), ("AuraScale", balls.AURA_SCALE), ("Twist", 0.4),
                ("Falloff", 5.0), ("Rise", 0.0), ("SparkAmt", 1.0), ("Flicker", 0.2), ("AuraEmis", 1.3),
                ("AuraStrength", 1.0), ("Spike", 1.0), ("IceAmt", 1.0), ("RimAmt", 1.0), ("MilkAmt", 0.5)]
GLOW_VECTORS = [("C1", (0.45, 0.12, 1.0)), ("C2", (0.1, 0.75, 1.0)), ("C3", (1.0, 0.85, 1.0))]
GLOW_MODES = ["aura", "glass"]                                                                 # Mode 0..1


def log(*a):
    unreal.log_warning("[EB] " + " ".join(str(x) for x in a))


def read(name):
    with open(os.path.join(HLSL, name)) as fo:
        s = fo.read()
    return s


def get_or_create(name, folder, cls, factory):
    """Reuse an existing asset (deleting referenced packages can fail in a commandlet), else create it."""
    path = folder + "/" + name
    if EAL.does_asset_exist(path):
        a = EAL.load_asset(path)
        if a is not None:
            return a
    return AT.create_asset(name, folder, cls, factory)


def import_file(src, dest_path, name):
    task = unreal.AssetImportTask()
    task.filename = src
    task.destination_path = dest_path
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = False
    AT.import_asset_tasks([task])
    asset = EAL.load_asset(dest_path + "/" + name)
    if asset is None:
        raise RuntimeError("import failed: " + src)
    return asset


def make_volume(atlas_png, name):
    tex = import_file(os.path.join(ROOT, "SourceArt", atlas_png), "/Game/SourceArt", name + "_Atlas")
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    vol = get_or_create(name, BASE, unreal.VolumeTexture, unreal.VolumeTextureFactory())
    vol.set_editor_property("srgb", False)
    vol.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    vol.set_editor_property("source2d_texture", tex)          # PostEditChange -> UpdateSourceFromSourceTexture
    vol.set_editor_property("source2d_tile_size_x", 64)
    vol.set_editor_property("source2d_tile_size_y", 64)
    vol.set_editor_property("address_mode", unreal.TextureAddress.TA_WRAP)
    vol.set_editor_property("never_stream", True)            # mips inline in the package (fast container mode)
    EAL.save_loaded_asset(tex)
    EAL.save_loaded_asset(vol)
    return vol


def preview_mesh(obj_name, asset_name):
    """make_meshes.py's OBJ as a static mesh for the editor previews (Nanite off: the game runs r.Nanite=0)."""
    sm = import_file(os.path.join(ROOT, "SourceArt", obj_name), "/Game/Preview", asset_name)
    ns = sm.get_editor_property("nanite_settings")
    if ns.get_editor_property("enabled"):
        ns.set_editor_property("enabled", False)
        sm.set_editor_property("nanite_settings", ns)
    EAL.save_loaded_asset(sm)
    return sm


def make_preview_ball():
    """Hi-poly UV sphere, radius 50 cm (like the game's SM_PlayerBall), for the aura shell in previews."""
    obj = os.path.join(ROOT, "SourceArt", "preview_ball.obj")
    seg, rings, R = 192, 96, 50.0
    with open(obj, "w") as fo:
        for i in range(rings + 1):
            th = math.pi * i / rings
            for j in range(seg + 1):
                ph = 2 * math.pi * j / seg
                x, y, z = math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)
                fo.write("v %f %f %f\nvn %f %f %f\nvt %f %f\n" % (x * R, y * R, z * R, x, y, z, j / seg, i / rings))
        for i in range(rings):
            for j in range(seg):
                a = i * (seg + 1) + j + 1
                b = a + seg + 1
                fo.write("f %d/%d/%d %d/%d/%d %d/%d/%d\n" % (a, a, a, b, b, b, a + 1, a + 1, a + 1))
                fo.write("f %d/%d/%d %d/%d/%d %d/%d/%d\n" % (a + 1, a + 1, a + 1, b, b, b, b + 1, b + 1, b + 1))
    return preview_mesh("preview_ball.obj", "SM_PreviewBall")


def expr(mat, cls, x, y, **props):
    e = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def params(mat, scalars, vectors, volumes):
    out, y = [], 0
    for n, v in scalars:
        out.append((n, expr(mat, unreal.MaterialExpressionScalarParameter, -900, y, parameter_name=n, default_value=v)))
        y += 60
    for n, v in vectors:
        out.append((n, expr(mat, unreal.MaterialExpressionVectorParameter, -900, y, parameter_name=n,
                            default_value=unreal.LinearColor(v[0], v[1], v[2], 1))))
        y += 120
    for n, vol in volumes:
        out.append((n, expr(mat, unreal.MaterialExpressionTextureObjectParameter, -900, y, parameter_name=n, texture=vol)))
        y += 120
    return out


def time_input(mat):
    time = expr(mat, unreal.MaterialExpressionTime, -1300, -200)
    toff = expr(mat, unreal.MaterialExpressionScalarParameter, -1300, -150, parameter_name="TimeOffset", default_value=0.0)
    tadd = expr(mat, unreal.MaterialExpressionAdd, -1100, -200)
    MEL.connect_material_expressions(time, "", tadd, "A")
    MEL.connect_material_expressions(toff, "", tadd, "B")
    return tadd


def local_pos(mat, y):
    wp = expr(mat, unreal.MaterialExpressionWorldPosition, -1300, y)
    lp = expr(mat, unreal.MaterialExpressionTransformPosition, -1100, y,
              transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
              transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    MEL.connect_material_expressions(wp, "", lp, "")
    return wp, lp


def to_local(mat, src, y):
    e = expr(mat, unreal.MaterialExpressionTransform, -1100, y,
             transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD,
             transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_LOCAL)
    MEL.connect_material_expressions(src, "", e, "")
    return e


def custom_node(mat, code, sources, extra_outputs, desc):
    custom = expr(mat, unreal.MaterialExpressionCustom, -400, 0, code=code,
                  output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3, description=desc)
    inputs = []
    for n, _ in sources:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)
    outs = []
    for n, ty in extra_outputs:
        co = unreal.CustomOutput()
        co.set_editor_property("output_name", n)
        co.set_editor_property("output_type", ty)
        outs.append(co)
    custom.set_editor_property("additional_outputs", outs)
    for n, src in sources:
        if not MEL.connect_material_expressions(src, "", custom, n):
            log("WARN connect failed", desc, n)
    return custom


def dispatch(fixed_sig, fixed_args, scalars, vectors, files, selector, outs_sig, outs_args, prologue, epilogue, tex2d=()):
    """HLSL for a master: common helpers, one struct per look (its file as the body of Run(...) with every input as a
    parameter), and a uniform branch on the selector."""
    sig = ", ".join(fixed_sig + ["float %s" % n for n, _ in scalars] + ["float3 %s" % n for n, _ in vectors]
                    + ["Texture3D NoiseTex", "SamplerState NoiseTexSampler", "Texture3D CellsTex", "SamplerState CellsTexSampler"]
                    + ["Texture2D %s, SamplerState %sSampler" % (n, n) for n in tex2d] + outs_sig)
    args = ", ".join(fixed_args + [n for n, _ in scalars] + ["%s.rgb" % n for n, _ in vectors]
                     + ["NoiseTex", "NoiseTexSampler", "CellsTex", "CellsTexSampler"]
                     + ["%s, %sSampler" % (n, n) for n in tex2d] + outs_args)
    parts = [read("common.hlsl")]
    for i, fn in enumerate(files):
        parts.append("struct EB_%d\n{\n\tfloat3 Run(%s)\n\t{\n%s\n\t}\n};\n" % (i, sig, read(fn + ".hlsl")))
    body = prologue
    for i in range(len(files)):
        cond = "[branch] if (%s < %g) " % (selector, i + 0.5) if i < len(files) - 1 else ""
        body += "%s%s{ EB_%d s; em = s.Run(%s); }\n" % ("else " if i else "", cond, i, args)
    return "\n".join(parts) + body + epilogue


def stats(mat, label):
    st = MEL.get_statistics(mat)
    log("STATS", label, "VS", st.num_vertex_shader_instructions, "PS", st.num_pixel_shader_instructions,
        "samplers", st.num_samplers, "ptex", st.num_pixel_texture_samples)


def proj_textures():
    """project_concepts.py's maps as textures (inline mips so the container needs no bulk data)."""
    out = {}
    for ball in ["void", "frost", "toxic"]:
        for kind in ["base", "emis", "norm"]:
            name = "T_Proj_%s_%s" % (ball.capitalize(), kind.capitalize())
            tex = import_file(os.path.join(ROOT, "SourceArt", "proj_%s_%s.png" % (ball, kind)), BASE, name)
            tex.set_editor_property("srgb", kind != "norm")
            tex.set_editor_property("never_stream", True)
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
            EAL.save_loaded_asset(tex)
            out[name] = tex
    return out


def build_ball_master(noise, cells, ptex):
    mat = get_or_create("M_EB_Ball", BASE, unreal.Material, unreal.MaterialFactoryNew())
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_CLEAR_COAT)
    mat.set_editor_property("tangent_space_normal", False)
    mat.set_editor_property("used_with_skeletal_mesh", False)
    mat.set_editor_property("use_material_attributes", True)
    _, lp = local_pos(mat, -400)
    cv = to_local(mat, expr(mat, unreal.MaterialExpressionCameraVectorWS, -1300, -300), -300)
    vn = to_local(mat, expr(mat, unreal.MaterialExpressionVertexNormalWS, -1300, -250), -250)
    # the camera's position and world up in the ball's local frame (FaceCam)
    caml = expr(mat, unreal.MaterialExpressionTransformPosition, -1100, -500,
                transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
                transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    MEL.connect_material_expressions(expr(mat, unreal.MaterialExpressionCameraPositionWS, -1300, -500), "", caml, "")
    upw = expr(mat, unreal.MaterialExpressionConstant3Vector, -1300, -550, constant=unreal.LinearColor(0, 0, 1, 1))
    upl = to_local(mat, upw, -550)
    sources = [("LP", lp), ("CV", cv), ("T", time_input(mat)), ("VN", vn), ("CamL", caml), ("UpL", upl)]
    sources += params(mat, BALL_SCALARS, BALL_VECTORS, [("NoiseTex", noise), ("CellsTex", cells)] +
                      [(n, ptex["T_Proj_Void_" + n[4:]]) for n in BALL_TEX2D])
    code = dispatch(["float3 LP", "float3 CV", "float T", "float3 VN", "float3 CamL", "float3 UpL"],
                    ["LP", "CV", "T", "VN", "CamL", "UpL"], BALL_SCALARS, BALL_VECTORS,
                    BALL_STYLES, "Style", ["out float3 BaseColorOut", "out float RoughOut", "out float3 NormalOut"],
                    ["bc", "ro", "nn"], "float3 bc = 0; float ro = 0.3; float3 nn = float3(0, 0, 1); float3 em = 0;\n",
                    "BaseColorOut = bc; RoughOut = ro; NormalOut = nn;\n"
                    # reflections fade toward the silhouette by GrazeCut (Fresnel would otherwise mirror the yellow
                    # start pad along the race ball's lower edge); Specular 0 also drops UE's grazing Fresnel
                    "float gnv = saturate(dot(normalize(LP), normalize(CV)));\n"
                    "GrazeOut = lerp(1.0, smoothstep(0.05, 0.6, gnv), saturate(GrazeCut));\nreturn em;\n", BALL_TEX2D)
    custom = custom_node(mat, code, sources,
                         [("BaseColorOut", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                          ("RoughOut", unreal.CustomMaterialOutputType.CMOT_FLOAT1),
                          ("NormalOut", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                          ("GrazeOut", unreal.CustomMaterialOutputType.CMOT_FLOAT1)], "EB_Ball")
    # Make Material Attributes: it has ClearCoat / ClearCoatRoughness pins, which the material's own pins
    # (MP_CustomData0/1) hide from Python. Reflection strength is a parameter: SpecAmt, CoatAmt, CoatRough.
    ma = expr(mat, unreal.MaterialExpressionMakeMaterialAttributes, 0, 0)
    nw = expr(mat, unreal.MaterialExpressionTransform, -150, 300,
              transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
              transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    MEL.connect_material_expressions(custom, "NormalOut", nw, "")
    links = [(custom, "", "EmissiveColor"), (custom, "BaseColorOut", "BaseColor"), (custom, "RoughOut", "Roughness"),
             (nw, "", "Normal"), (expr(mat, unreal.MaterialExpressionConstant, -150, 400, r=0.0), "", "Metallic")]
    for pname, val, pin, y in [("SpecAmt", 0.5, "Specular", 460), ("CoatAmt", 1.0, "ClearCoat", 520),
                               ("CoatRough", 0.1, "ClearCoatRoughness", 580)]:
        pe = expr(mat, unreal.MaterialExpressionScalarParameter, -400, y, parameter_name=pname, default_value=val)
        if pin != "ClearCoatRoughness":                       # x GrazeOut (fades reflections at grazing angles)
            mul = expr(mat, unreal.MaterialExpressionMultiply, -200, y)
            MEL.connect_material_expressions(pe, "", mul, "A")
            MEL.connect_material_expressions(custom, "GrazeOut", mul, "B")
            pe = mul
        links.append((pe, "", pin))
    for src, out, pin in links:
        if not MEL.connect_material_expressions(src, out, ma, pin):
            log("WARN attribute pin", pin)
    MEL.connect_material_property(ma, "", unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    return mat


def build_glow_master(noise, cells):
    mat = get_or_create("M_EB_Glow", BASE, unreal.Material, unreal.MaterialFactoryNew())
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    mat.set_editor_property("translucency_pass", unreal.MaterialTranslucencyPass.MTP_AFTER_DOF)
    mat.set_editor_property("used_with_skeletal_mesh", False)
    wp, lp = local_pos(mat, -600)
    cam = expr(mat, unreal.MaterialExpressionCameraVectorWS, -1300, -350)
    cvl = to_local(mat, cam, -700)
    vn = to_local(mat, expr(mat, unreal.MaterialExpressionVertexNormalWS, -1300, -250), -250)
    sources = [("LP", lp), ("CVL", cvl), ("WP", wp), ("OP", expr(mat, unreal.MaterialExpressionObjectPositionWS, -1300, -450)),
               ("CVW", cam), ("VN", vn), ("T", time_input(mat))]
    sources += params(mat, GLOW_SCALARS, GLOW_VECTORS, [("NoiseTex", noise), ("CellsTex", cells)])
    code = dispatch(["float3 LP", "float3 CVL", "float3 WP", "float3 OP", "float3 CVW", "float3 VN", "float T"],
                    ["LP", "CVL", "WP", "OP", "CVW", "VN", "T"], GLOW_SCALARS, GLOW_VECTORS, GLOW_MODES, "Mode", [], [],
                    "float3 em = 0;\n", "return em;\n")
    custom = custom_node(mat, code, sources, [], "EB_Glow")
    MEL.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    return mat


def instance(name, parent, overrides):
    mi = get_or_create(name, BASE, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    MEL.clear_all_material_instance_parameters(mi)
    for k, v in overrides.items():
        if isinstance(v, str):                                    # a texture of ours, by asset name
            MEL.set_material_instance_texture_parameter_value(mi, k, EAL.load_asset(BASE + "/" + v))
        elif isinstance(v, tuple):
            MEL.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(v[0], v[1], v[2], 1))
        else:
            MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    return mi


def main():
    noise = make_volume("T_EB_Noise_Atlas.png", "VT_EB_Noise")
    cells = make_volume("T_EB_Cells_Atlas.png", "VT_EB_Cells")
    make_preview_ball()
    meshes = sorted({m for parts in balls.ALL.values() for m, _, _, _ in parts if m not in ("aura", "ball")})
    for m in meshes:
        preview_mesh(m + ".obj", "SM_" + m)
    ptex = proj_textures()
    ball = build_ball_master(noise, cells, ptex)
    glow = build_glow_master(noise, cells)
    for parts in balls.ALL.values():
        for _, mi, master, overrides in parts:
            instance(mi, ball if master == "ball" else glow, overrides)
    stats(ball, "M_EB_Ball (all styles)")
    stats(glow, "M_EB_Glow (all modes)")
    log("DONE")


main()

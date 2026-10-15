// Concept-projected look (project_concepts.py's maps, equirect in ball space). The outer layer (stone / black glass /
// ice sheen) is ProjBase with ProjNorm's object-space normals, lit by the game. The glowing layer is ProjEmis drawn
// DEEPER (where the refracted view ray meets a shell ProjDepth below the surface: it shifts with the view), seen
// only where the surface itself is a gap in the outer layer, and slowly FLOWING: a two-phase flowmap along a swirling
// tangent field, so the glow streams without the picture turning rigidly. Uses: Emis (glow gain), ProjDepth, FlowAmt,
// FlowRate (flowmap cycles per second), FaceCam (1: the picture's front faces the camera), Speed, SheenAmt (base brightness), BakeAmt (how much of the picture's painted shading of the outer layer shows
// as-is, on top of the game's lighting), DetailAmt (micro facets + contrast up close), SparkleAmt (glints), ProjBase,
// ProjEmis (alpha: the picture's own edge mask, where the detail goes), ProjNorm.
// Crisp detail at Customize distance (the concepts are only ~330-600 px across): along the picture's own edges, fine
// facets tilt the normal and small glints twinkle, faded out with distance (the pixel footprint), so the design is
// unchanged and only gains sharpness up close.
EBF f;
float3 P = LP / Radius;
float3 Nn = normalize(P);
float3 D = normalize(-CV);
float t = T * Speed;
float px = max(length(fwidth(P)), 1e-4);
float lvl = max(0, log2(px / (6.2831853 / 2048.0)));      // mip from the pixel footprint (no seam derivatives)

// FaceCam (Customize, where the preview ball's turn is random): the picture's front faces the camera, world up kept up.
// The picture frame: x = -toward camera, y = screen right, z = up. Races use FaceCam 0 (the frame is the ball's own).
float3 fw = normalize(CamL), upL = normalize(UpL - fw * dot(UpL, fw)), rt = cross(upL, -fw);
bool fc = FaceCam > 0.5;
float3 Pn = fc ? float3(dot(Nn, -fw), dot(Nn, rt), dot(Nn, upL)) : Nn;     // the surface point in the picture frame

// outer layer
float2 uv0 = float2(atan2(Pn.y, Pn.x) / 6.2831853 + 0.5, acos(clamp(Pn.z, -1, 1)) / 3.14159265);
float3 base = ProjBase.SampleLevel(ProjBaseSampler, uv0, lvl).rgb;
float3 nrm = normalize(ProjNorm.SampleLevel(ProjNormSampler, uv0, lvl).rgb * 2 - 1);
if (fc) nrm = -fw * nrm.x + rt * nrm.y + upL * nrm.z;              // back to the ball's local frame
float4 emisTop4 = ProjEmis.SampleLevel(ProjEmisSampler, uv0, lvl);
float3 emisTop = emisTop4.rgb;
float edge = emisTop4.a;
float near = saturate(1.5 - lvl * 0.5);                     // detail only where the texture is magnified (close up)
float4 mc = f.V(CellsTex, CellsTexSampler, Nn * 9.0);
float4 mc2 = f.V(CellsTex, CellsTexSampler, Nn * 23.0 + 0.4);
float3 tA = normalize(cross(Nn, float3(0.31, 0.83, 0.47)));
float3 tB = cross(Nn, tA);
float3 micro = (tA * (mc.b - 0.5) + tB * (mc.a - 0.5)) * 0.6 + (tA * (mc2.a - 0.5) + tB * (mc2.b - 0.5)) * 0.4;
float detail = DetailAmt * near * (0.35 + 0.65 * edge);
float gap = saturate(dot(emisTop, float3(0.3, 0.6, 0.1)) * 5.0);   // where the outer layer lets the glow through

// glowing layer, deeper and flowing
float3 q = normalize(f.Shell(P, refract(D, Nn, 0.85), 1.0 - ProjDepth));
if (fc) q = float3(dot(q, -fw), dot(q, rt), dot(q, upL));
float3 sw = f.V(NoiseTex, NoiseTexSampler, q * 1.3 + float3(0, 0, t * 0.01)).gba - 0.5;
float3 flow = cross(q, sw);                                 // a swirling tangent field
float ph0 = frac(t * FlowRate), ph1 = frac(t * FlowRate + 0.5);   // drift speed ~ FlowAmt * FlowRate (rad/s)
float3 q0 = normalize(q + flow * (ph0 - 0.5) * FlowAmt);
float3 q1 = normalize(q + flow * (ph1 - 0.5) * FlowAmt);
float2 u0 = float2(atan2(q0.y, q0.x) / 6.2831853 + 0.5, acos(clamp(q0.z, -1, 1)) / 3.14159265);
float2 u1 = float2(atan2(q1.y, q1.x) / 6.2831853 + 0.5, acos(clamp(q1.z, -1, 1)) / 3.14159265);
float wgt = abs(ph0 * 2 - 1);
float3 glow = lerp(ProjEmis.SampleLevel(ProjEmisSampler, u0, lvl).rgb, ProjEmis.SampleLevel(ProjEmisSampler, u1, lvl).rgb, wgt);
glow = lerp(emisTop, glow, 0.75);                           // keep the picture's own shapes at the surface too
float3 em = glow * glow * 1.6 + glow * 0.4;                 // brightest parts bloom (sRGB-ish picture -> HDR)

base *= 1 + (mc2.r - 0.5) * 0.5 * detail;                    // fine mottling of the outer layer
float spark = (1 - smoothstep(0.0, 0.08, mc2.r)) * step(0.92, mc2.b) * edge * near;
spark *= 0.5 + 0.5 * sin(t * 6.0 + mc2.a * 50.0);
em += (glow * 2.0 + 0.6) * spark * SparkleAmt;
BaseColorOut = base * SheenAmt;
RoughOut = 0.12;
NormalOut = normalize(lerp(Nn, nrm, 0.8) + micro * detail * 0.35);
return em * lerp(0.15, 1.0, gap) * Emis + base * BakeAmt;

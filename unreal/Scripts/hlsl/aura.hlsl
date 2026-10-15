// Aura: a soft additive glow just outside the ball (the host scales a sphere by AuraScale round the ball).
// The ball keeps a crisp edge: nothing is drawn over it. Outside, a smooth glow falls off from the silhouette; inside
// that glow, short soft licks (flame / mist / vapour, by the instance's settings) drift outward and a few sparks are
// thrown off. One dial, AuraStrength (0 = none, 1 = full), scales it all.
// Works in WORLD space round the object's centre, so the aura doesn't roll with the ball.
// Sizes are measured in the shell's LOCAL space against ShellRadius (the sphere's radius in its mesh units), because
// a dynamic mesh's bounds radius is its box's (r * sqrt 3); directions come from world space (no rolling).
// Inputs: LP (local position), CVL (camera vector, local), WP, OP (object centre, world), CVW (camera vector, world),
// ShellRadius, T, Speed,
// AuraScale, Twist, Falloff, Rise, SparkAmt, Flicker, AuraEmis, AuraStrength, C1 (inner colour), C2 (outer colour),
// C3 (sparks), NoiseTex, CellsTex.
EBF f;
float3 c1 = C1.rgb, c2 = C2.rgb, c3 = C3.rgb;
float3 Dw = normalize(-CVW);
float3 Dl = normalize(-CVL);
float3 pl = LP / ShellRadius;
float h = length(pl - Dl * dot(pl, Dl));          // the view ray's closest approach to the centre: 0 .. 1 silhouette
float rb = 1.0 / AuraScale;                       // the ball's silhouette radius
float3 pw = WP - OP;
float3 cw = pw - Dw * dot(pw, Dw);
float3 dir = cw / max(length(cw), 1e-4);          // world-space direction of that point (doesn't roll)
float t = T * Speed;
float x = saturate((h - rb) / (1 - rb));          // 0 at the ball's edge .. 1 at the shell's edge
float outside = smoothstep(rb, rb + 0.004, h);    // crisp: nothing over the ball itself
float3 up = float3(0, 0, 1);

float3 sd = f.RotAxis(dir, Dw, x * Twist + t * 0.1);
// soft licks: per-direction reach that evolves with time, short (a fraction of the glow)
float nA = f.V(NoiseTex, NoiseTexSampler, sd * 1.1 + float3(0, 0, t * 0.1)).r;
float reach = 0.18 + 0.45 * Spike * smoothstep(0.35, 0.85, nA) + Rise * 0.5 * saturate(dot(dir, up));
float lick = smoothstep(0.0, 0.5, reach - x);
// texture inside streams outward
float3 q = sd * (2.0 + 1.4 * x - 0.5 * t) - up * t * Rise;
float n2 = f.V(NoiseTex, NoiseTexSampler, q * 0.8).r;
float flick = 1 + Flicker * (f.V(NoiseTex, NoiseTexSampler, float3(t * 0.31, 0.2, 0.7)).r - 0.5) * 2;

float shellFade = 1 - smoothstep(0.75, 1.0, h);
float halo = exp(-x * Falloff);
float glow = halo * 0.6 + lick * (0.35 + 0.35 * n2) * (1 - x) * saturate(Spike * 1.5);

float3 qs = sd * (3.0 + 2.2 * x - 1.3 * t) - up * t * Rise * 1.5;
float4 cs = f.V(CellsTex, CellsTexSampler, qs * 0.8);
float spark = (1 - smoothstep(0.0, 0.12, cs.r)) * step(0.88, cs.b) * (1 - x);
spark *= 0.55 + 0.45 * sin(t * 9 + cs.a * 40);

float3 col = lerp(c1, c2, saturate(x * 1.8)) * glow * flick + c3 * spark * SparkAmt * 2.0;
return col * outside * shellFade * AuraEmis * AuraStrength;

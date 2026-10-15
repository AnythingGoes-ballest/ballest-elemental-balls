// Frost's glass shell (additive): a bright cold rim, a soft milky frost band toward the silhouette (the concept's
// soft bright outer zone), a little frosty texture in it, and a sharp highlight. Uses: ShellRadius (49.3), RimAmt,
// MilkAmt, C2 (frost colour), NoiseTex.
EBF f;
float3 Dl = normalize(-CVL);
float3 n = normalize(LP);
float NoV = saturate(dot(n, -Dl));
float4 nz = f.V(NoiseTex, NoiseTexSampler, n * 3.0);
float rim = pow(1 - NoV, 3.5) * RimAmt;
float milk = smoothstep(0.35, 0.9, 1 - NoV) * MilkAmt * (0.75 + 0.5 * nz.r);
float3 Lw = normalize(float3(-0.45, 0.35, 0.82));
float spec = pow(saturate(dot(reflect(Dl, n), Lw)), 400.0) * 2.0;
return (C2.rgb * (rim + milk) + float3(1, 1, 1) * spec) * AuraEmis;

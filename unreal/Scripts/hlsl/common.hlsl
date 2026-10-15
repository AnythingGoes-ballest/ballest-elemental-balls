// Shared helpers for the Elemental Balls v2 Custom nodes (pasted in front of each ball's code by build_materials.py).
// UE Custom nodes can't declare free functions, so they live as methods of a struct.
// Inputs every ball gets: LP (local position, cm), CV (camera vector in local space: pixel -> camera),
// T (seconds), Radius (ball radius in local units, 50 for the game's SM_PlayerBall).
struct EBF
{
	// Ray from the outer surface point p (unit sphere) going along d: where does it meet the shell of radius r?
	// A grazing ray that misses the shell returns its closest approach (keeps the rim continuous).
	float3 Shell(float3 p, float3 d, float r)
	{
		float b = dot(p, d);
		float c = dot(p, p) - r * r;
		float disc = b * b - c;
		float t = disc > 0 ? (-b - sqrt(disc)) : -b;
		return p + d * max(t, 0);
	}
	float4 V(Texture3D tex, SamplerState s, float3 p)
	{
		return tex.SampleLevel(s, p, 0);
	}
	float3 RotAxis(float3 p, float3 a, float ang)
	{
		float s = sin(ang), c = cos(ang);
		return p * c + cross(a, p) * s + a * dot(a, p) * (1 - c);
	}
	float Hash(float n)
	{
		return frac(sin(n * 12.9898) * 43758.5453);
	}
	float Ridge(float n)
	{
		return 1 - abs(n * 2 - 1);
	}
	float2 Hash2(float2 p)
	{
		return frac(sin(float2(dot(p, float2(127.1, 311.7)), dot(p, float2(269.5, 183.3)))) * 43758.5453);
	}
	// Analytic 2D Voronoi, periodic in x with period perX (cells). Returns F2 - F1 (0 on a border: crisp straight
	// edges), the cell id (0..1) and the offset from the pixel to its cell's site (for facet shading).
	float4 Voronoi(float2 x, float perX, out float2 toSite)
	{
		float2 n = floor(x), fr = x - n;
		float f1 = 8, f2 = 8, id = 0;
		toSite = 0;
		[unroll] for (int j = -1; j <= 1; j++)
		[unroll] for (int i = -1; i <= 1; i++)
		{
			float2 g = float2(i, j);
			float2 cell = n + g;
			cell.x = cell.x - perX * floor(cell.x / perX);
			float2 o = 0.15 + 0.7 * Hash2(cell);
			float2 r = g + o - fr;
			float d = dot(r, r);
			if (d < f1) { f2 = f1; f1 = d; id = frac(sin(dot(cell, float2(41.3, 289.1))) * 9631.7); toSite = r; }
			else if (d < f2) { f2 = d; }
		}
		return float4(sqrt(f2) - sqrt(f1), id, sqrt(f1), 0);
	}
};

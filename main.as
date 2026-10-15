// Elemental Balls: three balls made of layers, through Cosmetic Kit (a dependency: see info.toml). Each is a model
// (models/<ball>.txt): spheres and plates in the game's own materials, set up with the plugin's pictures, some of
// them turning and some of their colours moving, so the light inside shifts and flows under the glossy surface.
//   Void Crystal: thick obsidian plates with glowing crystal turning underneath.
//   Frost: white ice blades swirling round a deep blue, sparkling core, inside clear glass.
//   Toxic Current: neon green and teal liquid streaming inside black glass.

import bool AddBall(const string &in, const string &in, const string &in, const string &in, const string &in) from "cosmetic-kit";

// Each ball reads its meshes when added (measured: 5 to 16 ms a ball),
// so they're added one a frame, as Glass Balls does: all at once could go over the plugin's time budget.
const array<string> kIds = {"void", "frost", "toxic"};
const array<string> kNames = {"Void Crystal", "Frost", "Toxic Current"};
int added = 0;
// v2: the balls wear real cooked materials from assets/ (models/v2_*.txt). "" = the v1 game-material models.
const string kModel = "v2_";

void Update(float dt)
{
    if (added >= int(kIds.length())) return;
    string f = Plugins::Folder();
    string id = kIds[added];
    AddBall("elemental-balls." + id, kNames[added], "", f + "previews/" + id + ".png", f + "models/" + kModel + id + ".txt");
    added++;
}

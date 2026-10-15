# Cooks and stages the elemental_balls content project as an IoStore container (pm-assets recipe, DX12 SM6).
# Output: <proj>\Saved\StagedBuilds\Windows\elemental-balls\Content\Paks\elemental_balls-Windows.{pak,utoc,ucas}
# (that full container also carries engine content; the recipe's slim step keeps only Content/Mods/elemental_balls/
# and ShaderArchive-elemental_balls-PCD3D_SM6).
param([string]$Log = "$env:TEMP\eb_cook.log")
$proj = Join-Path (Split-Path $PSScriptRoot -Parent) "elemental_balls.uproject"
& "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun "-project=$proj" -noP4 -platform=Win64 `
    -clientconfig=Shipping -cook -stage -pak -iostore -unattended -nocompileeditor -nocompile -utf8output *> $Log
"exit $LASTEXITCODE (log: $Log)"

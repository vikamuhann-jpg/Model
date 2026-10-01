# Populate the Linux wheelhouse from Windows.
# WSL on this machine has no outbound network, so wheels are fetched here and
# consumed offline inside WSL by scripts/setup_wsl.sh.
$ErrorActionPreference = "Stop"
$Wheelhouse = "C:\Users\vikam\flowguard_data\wheelhouse"
New-Item -ItemType Directory -Force -Path $Wheelhouse | Out-Null

# Target the WSL interpreter (Ubuntu 24.04 ships CPython 3.12), not this host.
# --platform matches wheel tags exactly and implies no backward compatibility,
# so every manylinux generation in use must be listed: snapml tags _2_28,
# matplotlib only tags _2_17.
python -m pip download `
  snapml==1.17.2 scikit-learn xgboost pandas pyarrow networkx shap pyyaml matplotlib pytest `
  pip setuptools wheel `
  --only-binary :all: --python-version 3.12 `
  --platform manylinux_2_28_x86_64 `
  --platform manylinux_2_17_x86_64 `
  --platform manylinux2014_x86_64 `
  -d $Wheelhouse

Write-Host "wheelhouse: $((Get-ChildItem $Wheelhouse -Filter *.whl).Count) wheels"

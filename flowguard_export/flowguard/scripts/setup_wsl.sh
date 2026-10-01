#!/usr/bin/env bash
# Bootstrap the FlowGuard environment inside WSL2 Ubuntu.
#
# Runs fully offline from a local wheelhouse, because this machine's WSL has no
# outbound network (apt and pypi both unreachable -- see docs/README.md).
# Refresh the wheelhouse from Windows with scripts/refresh_wheelhouse.ps1.
set -euo pipefail

WHEELHOUSE="${WHEELHOUSE:-/mnt/c/Users/vikam/flowguard_data/wheelhouse}"
VENV="${VENV:-$HOME/flowguard/.venv}"

[[ -d "$WHEELHOUSE" ]] || { echo "ERROR: wheelhouse not found: $WHEELHOUSE" >&2; exit 1; }

echo "==> creating venv at $VENV"
mkdir -p "$(dirname "$VENV")"
rm -rf "$VENV"
# python3.12-venv is not installed and apt is unreachable, so skip ensurepip
# and bootstrap pip from the wheelhouse instead.
python3 -m venv --without-pip "$VENV"
PYTHONPATH="$(ls "$WHEELHOUSE"/pip-*.whl | head -1)" \
  "$VENV/bin/python" -m pip install -q --no-index --find-links="$WHEELHOUSE" pip setuptools wheel

echo "==> installing dependencies"
PIP=("$VENV/bin/python" -m pip install -q --no-index --find-links="$WHEELHOUSE")
"${PIP[@]}" snapml==1.17.2 scikit-learn pandas pyarrow networkx shap pyyaml matplotlib pytest
# xgboost declares nvidia-nccl-cu13 on Linux for multi-GPU only; this is CPU-bound.
"${PIP[@]}" --no-deps xgboost

echo "==> satisfying libgomp.so.1 (snapml's OpenMP dependency)"
if ! "$VENV/bin/python" -c "import snapml" 2>/dev/null; then
  SRC=$(ls "$VENV"/lib/python3.12/site-packages/scikit_learn.libs/libgomp-*.so.1.0.0 | head -1)
  # Must land in a default loader search path under this exact filename:
  # ldconfig indexes by SONAME, which in the vendored copy is libgomp-<hash>.so.1.0.0.
  sudo install -m 0755 "$SRC" /usr/lib/x86_64-linux-gnu/libgomp.so.1
  sudo ldconfig
fi

echo "==> installing flowguard (editable)"
# --no-build-isolation: an isolated build env would try to fetch setuptools from
# the network, which is unreachable. setuptools is already in the venv.
REPO="$(dirname "$(dirname "$(realpath "$0")")")"
"$VENV/bin/python" -m pip install -q --no-index --no-deps --no-build-isolation -e "$REPO"

echo "==> verifying the GFP gate"
"$VENV/bin/python" -m pytest "$REPO/tests/integration/test_gfp_environment.py" -q

echo
echo "OK. Activate with: source $VENV/bin/activate"

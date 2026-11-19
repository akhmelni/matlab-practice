#!/bin/sh
# Start the MATLAB Practice app (macOS / Linux). Opens it in your browser.
cd "$(dirname "$0")" || exit 1
if ! command -v uv >/dev/null 2>&1; then
  echo "uv isn't installed. See INSTALL.md."
  exit 1
fi
exec uv run practice "$@"

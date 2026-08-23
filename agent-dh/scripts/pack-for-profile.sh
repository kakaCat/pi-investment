#!/usr/bin/env bash
# Pack agent-dh packages for DSH profile installation
# Usage: ./scripts/pack-for-profile.sh [output-dir]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${1:-$HOME/.dsh/profiles/investment/local-packages}"

echo "📦 Packing agent-dh packages for profile..."
echo "  Source: $PROJECT_ROOT"
echo "  Output: $OUTPUT_DIR"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Build all packages first
echo ""
echo "🔨 Building packages..."
cd "$PROJECT_ROOT"
pnpm build

# Pack each package
echo ""
echo "📦 Packing packages..."

PACKAGES=(
  "agent-os-client"
  "competition"
  "data-manager"
  "evolution"
  "evolver"
  "factor"
  "genome"
  "intelligence"
  "investment"
  "learning"
  "lifecycle"
  "market"
  "memory"
  "model"
  "notification"
  "risk"
  "scheduler"
  "strategy"
  "trading"
)

for pkg in "${PACKAGES[@]}"; do
  echo "  Packing @pi-investment/$pkg..."
  cd "$PROJECT_ROOT/packages/$pkg"

  # Use pnpm pack to create tarball
  TARBALL=$(pnpm pack --pack-destination "$OUTPUT_DIR" 2>&1 | grep "pi-investment-$pkg" | tail -1)

  if [ -z "$TARBALL" ]; then
    echo "    ❌ Failed to pack $pkg"
    exit 1
  fi

  echo "    ✅ Created $(basename "$TARBALL")"
done

# Pack quantsys-v2-client (at repo root)
echo "  Packing @pi-investment/quantsys-v2-client..."
cd "$PROJECT_ROOT/../quantsys-v2-client"
TARBALL=$(pnpm pack --pack-destination "$OUTPUT_DIR" 2>&1 | grep "pi-investment-quantsys-v2-client" | tail -1)
echo "    ✅ Created $(basename "$TARBALL")"

echo ""
echo "✅ All packages packed to: $OUTPUT_DIR"
echo ""
echo "📝 Next steps:"
echo "  1. cd ~/.dsh/profiles/investment"
echo "  2. Update package.json to use: \"file:local-packages/pi-investment-xxx-*.tgz\""
echo "  3. Run: pnpm install"

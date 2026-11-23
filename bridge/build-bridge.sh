#!/usr/bin/env bash
# Builds the Discord Social SDK bridge on Linux (needs cmake and g++/clang, C++20).
# Put the Discord Social SDK zip contents in bridge/sdk/ first (see PUT_SDK_HERE.txt).
set -euo pipefail
cd "$(dirname "$0")"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
echo "Bridge built: build/dcbridge"

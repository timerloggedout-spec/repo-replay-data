#!/bin/bash
# Usage: ./compile_run.sh [number_of_ranks]
# Default ranks = 2
#
# Requires:
#   - Kokkos (with desired backend: CUDA, HIP, SYCL, OpenMP, etc.)
#   - heFFTe (built with Kokkos support)
#   - MPI

set -e

RANKS=${1:-2}
BUILD_DIR="build"

if [ ! -d "src" ] || [ ! -f "CMakeLists.txt" ]; then
    echo "Please run from the project root directory."
    exit 1
fi

# Load modules if on HPC system (uncomment and adjust as needed)
# module load kokkos heffte mpich

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Configure with CMake
# Set Kokkos backend via -DKokkos_ENABLE_* options
# Example for OpenMP: -DKokkos_ENABLE_OPENMP=ON
# Example for CUDA: -DKokkos_ENABLE_CUDA=ON
# Example for SYCL: -DKokkos_ENABLE_SYCL=ON
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DKokkos_ENABLE_OPENMP=ON \
    -DKokkos_ENABLE_SERIAL=ON

# Build
make -j$(nproc)

# Run with MPI
echo "Running with $RANKS MPI ranks..."
mpirun -np "$RANKS" ./fft_kokkos_heffte
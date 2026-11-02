#include <mpi.h>
#include <Kokkos_Core.hpp>
#include <heffte.h>

#include <iostream>
#include <vector>
#include <cmath>
#include <complex>
#include <cassert>

// Use double precision
using scalar_type = double;
using complex_type = std::complex<scalar_type>;

int main(int argc, char* argv[]) {
    MPI_Init(&argc, &argv);

    int rank, nRanks;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &nRanks);

    // Initialize Kokkos
    Kokkos::initialize(argc, argv);

    if (rank == 0) {
        std::cout << "=== Kokkos + heFFTe Distributed FFT ===\n";
        std::cout << "Kokkos default device: "
                  << Kokkos::DefaultExecutionSpace::name() << "\n";
    }

    // Problem size: 3D FFT (Nx x Ny x Nz)
    // Must be divisible by nRanks in each dimension for slab decomposition
    const int NX = 64;
    const int NY = 64;
    const int NZ = 64;
    const int N_TOTAL = NX * NY * NZ;

    // Use a 1D slab decomposition along the first dimension
    // Each rank gets (NX / nRanks) slabs in the X direction
    if (NX % nRanks != 0) {
        if (rank == 0) {
            std::cerr << "Error: NX (" << NX << ") must be divisible by "
                      << "number of ranks (" << nRanks << ")\n";
        }
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    const int LOCAL_NX = NX / nRanks;
    const size_t LOCAL_SIZE = LOCAL_NX * NY * NZ;

    if (rank == 0) {
        std::cout << "Global FFT size: " << NX << " x " << NY << " x " << NZ
                  << " = " << N_TOTAL << " elements\n";
        std::cout << "Local size per rank: " << LOCAL_NX << " x " << NY << " x " << NZ
                  << " = " << LOCAL_SIZE << " elements\n";
        std::cout << "Using " << nRanks << " MPI ranks\n";
    }

    // ----------------------------------------------------------------------
    // 1. Define the grid mapping for heFFTe
    //    Slab decomposition: each rank owns a contiguous slab along X
    // ----------------------------------------------------------------------
    std::array<int, 3> global_dims = {NX, NY, NZ};
    std::array<int, 3> local_dims = {LOCAL_NX, NY, NZ};

    // Create a box (volume) for the data owned by this rank
    // Rank r owns slabs [r*LOCAL_NX, (r+1)*LOCAL_NX - 1] in X
    std::array<int, 3> low_bounds = {rank * LOCAL_NX, 0, 0};
    std::array<int, 3> high_bounds = {(rank + 1) * LOCAL_NX - 1, NY - 1, NZ - 1};

    heffte::box3d<int> local_box(low_bounds, high_bounds);

    // The global box covers the entire domain
    std::array<int, 3> global_low = {0, 0, 0};
    std::array<int, 3> global_high = {NX - 1, NY - 1, NZ - 1};
    heffte::box3d<int> global_box(global_low, global_high);

    // Create the grid mapping (slab decomposition)
    // heffte::grid_map<heffte::decomposition::slab> map(global_box, local_box, MPI_COMM_WORLD);
    // Use the newer API with shape
    heffte::shape3d<int> grid_shape(global_dims);
    heffte::grid_map<heffte::decomposition::slab> map(
        grid_shape,
        local_box,
        MPI_COMM_WORLD
    );

    // ----------------------------------------------------------------------
    // 2. Create the FFT plan with heFFTe
    //    Backend selection: heFFTe will use the best available backend
    //    (FFTW for CPU, cuFFT/rocFFT/oneMKL for GPU)
    // ----------------------------------------------------------------------
    // Use heFFTe's default backend (auto-selects based on available libraries)
    using backend_tag = heffte::backend::default_backend;

    // Create a 3D complex-to-complex FFT plan
    heffte::fft3d<backend_tag, scalar_type> fft_plan(map);

    if (rank == 0) {
        std::cout << "heFFTe plan created successfully\n";
    }

    // ----------------------------------------------------------------------
    // 3. Allocate data using Kokkos Views (device-agnostic)
    // ----------------------------------------------------------------------
    // Use 1D Views for simplicity (heFFTe expects contiguous memory)
    using view_type = Kokkos::View<complex_type*, Kokkos::DefaultExecutionSpace>;

    // Host mirror for initialization and verification
    using host_view_type = Kokkos::View<complex_type*, Kokkos::HostSpace>;

    // Allocate device memory
    view_type d_data("d_fft_data", LOCAL_SIZE);
    view_type d_work("d_work_data", LOCAL_SIZE);

    // Allocate host memory
    host_view_type h_data("h_fft_data", LOCAL_SIZE);
    host_view_type h_result("h_result", LOCAL_SIZE);

    // ----------------------------------------------------------------------
    // 4. Initialize data on host with a simple signal
    // ----------------------------------------------------------------------
    auto h_data_host = Kokkos::create_mirror_view(h_data);
    for (size_t i = 0; i < LOCAL_SIZE; ++i) {
        // Each rank gets a unique signal based on global index
        size_t global_idx = i + rank * LOCAL_SIZE;
        scalar_type val = static_cast<scalar_type>(global_idx) / N_TOTAL;
        h_data_host(i) = complex_type(val, 0.0);
    }
    Kokkos::deep_copy(h_data, h_data_host);

    // Copy host data to device
    Kokkos::deep_copy(d_data, h_data);

    // ----------------------------------------------------------------------
    // 5. Execute forward FFT
    // ----------------------------------------------------------------------
    // heFFTe expects pointers to the data
    // The transform is performed in-place
    fft_plan.forward(
        d_data.data(),
        d_work.data()
    );

    // Ensure all work is complete
    Kokkos::fence();

    // ----------------------------------------------------------------------
    // 6. Execute inverse FFT
    // ----------------------------------------------------------------------
    fft_plan.backward(
        d_data.data(),
        d_work.data()
    );

    Kokkos::fence();

    // ----------------------------------------------------------------------
    // 7. Verify: backward(forward(x)) should equal x * N_TOTAL
    // ----------------------------------------------------------------------
    Kokkos::deep_copy(h_result, d_data);

    auto h_result_host = Kokkos::create_mirror_view(h_result);
    Kokkos::deep_copy(h_result_host, h_result);

    bool ok = true;
    const scalar_type tol = 1e-6;

    for (size_t i = 0; i < LOCAL_SIZE && ok; ++i) {
        scalar_type expected = static_cast<scalar_type>(i + rank * LOCAL_SIZE) / N_TOTAL;
        expected *= N_TOTAL; // Backward(Forward(x)) = x * N
        scalar_type got = h_result_host(i).real();

        if (std::abs(got - expected) > tol) {
            ok = false;
            if (rank == 0 && i < 10) {
                std::cerr << "Mismatch at index " << i
                          << ": expected " << expected
                          << ", got " << got << "\n";
            }
        }
    }

    // All ranks must agree
    int all_ok = ok ? 1 : 0;
    int global_ok = 0;
    MPI_Allreduce(&all_ok, &global_ok, 1, MPI_INT, MPI_MIN, MPI_COMM_WORLD);

    if (rank == 0) {
        if (global_ok) {
            std::cout << "✓ FFT test PASSED on all ranks.\n";
        } else {
            std::cout << "✗ FFT test FAILED on at least one rank.\n";
        }
    }

    // ----------------------------------------------------------------------
    // 8. Optional: Print performance summary
    // ----------------------------------------------------------------------
    // heFFTe doesn't provide built-in timing, but you can add it around the
    // forward/backward calls using Kokkos::Timer or MPI_Wtime()

    // Cleanup
    Kokkos::finalize();
    MPI_Finalize();

    return 0;
}
cmake_minimum_required(VERSION 3.15)
project(FFT_KOKKOS_HEFFTE LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find MPI
find_package(MPI REQUIRED)

# Find Kokkos
find_package(Kokkos REQUIRED)

# Find heFFTe
find_package(heFFTe REQUIRED)

add_executable(fft_kokkos_heffte src/main.cpp)

target_link_libraries(fft_kokkos_heffte
    PRIVATE
    MPI::MPI_CXX
    Kokkos::kokkos
    heFFTe::heFFTe
)

target_compile_options(fft_kokkos_heffte PRIVATE -O3 -g)

install(TARGETS fft_kokkos_heffte DESTINATION bin)
# SPDX-License-Identifier: Apache-2.0
# Builds the extension module splintercam._kernels from every kernel/ folder under src/splintercam
# (ADR 0004; docs/dev/02 and 04). scikit-build-core runs it from pyproject.toml.

cmake_minimum_required(VERSION 3.28...4.1)
# C only for Shewchuk's predicates.c, vendored unchanged (ADR 0009).
project(splintercam_kernels LANGUAGES C CXX)

# C++20 features plus std::expected, which MSVC, GCC and Clang provide only in C++23 mode
# (docs/dev/04; decision of 2026-09-24/26 in plan 0001).
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON) # static libraries go into the extension module
set(CMAKE_EXPORT_COMPILE_COMMANDS ON) # clang-tidy reads it (tools/lint)

find_package(Python 3.13 REQUIRED COMPONENTS Interpreter Development.Module)
find_package(nanobind CONFIG REQUIRED)

# Test build with AddressSanitizer and UndefinedBehaviorSanitizer, used by `tools/test --all`
# (docs/dev/04, C++ kernels). It instruments Clipper2 and nanobind too, so it is set before them,
# and turns on the standard-library hardening of libstdc++ and libc++ (their own documentation).
option(SPLINTERCAM_SANITIZE "Build the kernels with ASan, UBSan and standard-library hardening" OFF)
if(SPLINTERCAM_SANITIZE)
  if(MSVC)
    message(FATAL_ERROR "SPLINTERCAM_SANITIZE is for GCC and Clang (Linux and macOS)")
  endif()
  set(SPLINTERCAM_SANITIZER_FLAGS -fsanitize=address,undefined -fno-sanitize-recover=all
                              -fno-omit-frame-pointer)
  add_compile_options(${SPLINTERCAM_SANITIZER_FLAGS})
  add_link_options(${SPLINTERCAM_SANITIZER_FLAGS})
  add_compile_definitions(_GLIBCXX_ASSERTIONS
                          _LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE)
endif()

# Kernel libraries, fetched at pinned versions (architecture/modules.yaml, kernel_libraries).
# SYSTEM: warnings inside third-party headers do not fail our build; our own code keeps them as
# errors (decision of 2026-09-26 in plan 0001). Their install rules are left out of the wheel,
# which installs only the "splintercam" component (pyproject.toml).
include(FetchContent)
# Fetched libraries build as static libraries inside the extension; a shared one would not be
# installed into the wheel.
set(BUILD_SHARED_LIBS OFF)
# Clipper2 2.0.1, BSL-1.0: offsets and Booleans (RESEARCH 02 and 17). No tests, examples or Z coordinate.
set(CLIPPER2_UTILS OFF CACHE BOOL "" FORCE)
set(CLIPPER2_EXAMPLES OFF CACHE BOOL "" FORCE)
set(CLIPPER2_TESTS OFF CACHE BOOL "" FORCE)
set(CLIPPER2_USINGZ OFF CACHE STRING "" FORCE)
FetchContent_Declare(Clipper2
  URL https://github.com/AngusJohnson/Clipper2/releases/download/Clipper2_2.0.1/Clipper2_2.0.1.zip
  URL_HASH SHA256=63e893fc40c3453c9d14cbe98bc7647f16a9d5846ae25b513d8a1ed5b8421144
  SOURCE_SUBDIR CPP
  SYSTEM)
FetchContent_MakeAvailable(Clipper2)

# Warnings are errors (docs/dev/04, C++ kernels). Strict floating point for every kernel source: no
# contraction into fused multiply-adds, no fast-math (D-097; geometry2d SPEC, REQ-G2D-014), so the
# exact arithmetic holds and constructions round the same way on every compiler.
if(MSVC)
  set(SPLINTERCAM_CXX_OPTIONS /W4 /WX /permissive- /fp:precise)
else()
  set(SPLINTERCAM_CXX_OPTIONS -Wall -Wextra -Wpedantic -Werror -ffp-contract=off -fno-fast-math)
endif()

# Assertions stay on in the Release builds the tests run against (docs/dev/04, errors). A release
# package may turn them off: -C cmake.define.SPLINTERCAM_KERNEL_ASSERTIONS=OFF.
# NDEBUG is removed from the optimised configurations rather than undefined again, because MSVC
# warns (D9025) when /UNDEBUG overrides /DNDEBUG. This applies to nanobind's own sources too.
option(SPLINTERCAM_KERNEL_ASSERTIONS "Keep assert() active in Release builds of the kernels" ON)
if(SPLINTERCAM_KERNEL_ASSERTIONS)
  foreach(config RELEASE RELWITHDEBINFO MINSIZEREL)
    string(REGEX REPLACE "[-/]DNDEBUG" "" CMAKE_CXX_FLAGS_${config} "${CMAKE_CXX_FLAGS_${config}}")
  endforeach()
endif()

# Kernel sources are src/splintercam/<module>/kernel/*.cpp (strategies: src/splintercam/strategies/<name>/kernel/).
# Each folder's bindings.cpp goes into the extension; all other kernel files go into a library that
# has neither nanobind nor Python on its include path, so only bindings.cpp can include nanobind
# (docs/dev/03, rule 3).
file(GLOB_RECURSE SPLINTERCAM_KERNEL_SOURCES CONFIGURE_DEPENDS "${PROJECT_SOURCE_DIR}/src/splintercam/*.cpp"
     "${PROJECT_SOURCE_DIR}/src/splintercam/*.c")
# Vendored code in kernel/vendor/ is not listed: a wrapper in kernel/ includes it (ADR 0009).
list(FILTER SPLINTERCAM_KERNEL_SOURCES INCLUDE REGEX "/kernel/[^/]+\\.c(pp)?$")
set(SPLINTERCAM_BINDING_SOURCES ${SPLINTERCAM_KERNEL_SOURCES})
list(FILTER SPLINTERCAM_BINDING_SOURCES INCLUDE REGEX "/bindings\\.cpp$")
list(FILTER SPLINTERCAM_KERNEL_SOURCES EXCLUDE REGEX "/bindings\\.cpp$")

# One submodule per kernel folder, splintercam._kernels.<module> ("/" becomes "_"), registered by
# splintercam::<module>::bind(nanobind::module_&) from that folder's bindings.cpp. The entry point is
# generated, so a module adds a kernel without editing a shared file.
set(SPLINTERCAM_KERNEL_DECLARATIONS "")
set(SPLINTERCAM_KERNEL_REGISTRATIONS "")
foreach(binding IN LISTS SPLINTERCAM_BINDING_SOURCES)
  cmake_path(RELATIVE_PATH binding BASE_DIRECTORY "${PROJECT_SOURCE_DIR}/src/splintercam"
             OUTPUT_VARIABLE relative)
  string(REGEX REPLACE "/kernel/bindings\\.cpp$" "" module "${relative}")
  string(REPLACE "/" "::" namespace "${module}")
  string(REPLACE "/" "_" submodule "${module}")
  string(APPEND SPLINTERCAM_KERNEL_DECLARATIONS
         "namespace splintercam::${namespace} {\nvoid bind(nanobind::module_& m);\n}\n")
  string(APPEND SPLINTERCAM_KERNEL_REGISTRATIONS
         "    {\n        auto sub = m.def_submodule(\"${submodule}\");\n"
         "        splintercam::${namespace}::bind(sub);\n    }\n")
endforeach()
configure_file(cmake/kernels_bindings.cpp.in
               "${PROJECT_BINARY_DIR}/generated/kernels_bindings.cpp" @ONLY)

# NOMINSIZE: nanobind would otherwise optimise the module for size instead of speed.
nanobind_add_module(_kernels NOMINSIZE
                    "${PROJECT_BINARY_DIR}/generated/kernels_bindings.cpp" ${SPLINTERCAM_BINDING_SOURCES})
target_compile_options(_kernels PRIVATE ${SPLINTERCAM_CXX_OPTIONS})

if(SPLINTERCAM_KERNEL_SOURCES)
  add_library(splintercam_kernel_code STATIC ${SPLINTERCAM_KERNEL_SOURCES})
  set_target_properties(splintercam_kernel_code PROPERTIES POSITION_INDEPENDENT_CODE ON)
  target_compile_options(splintercam_kernel_code PRIVATE
                         $<$<COMPILE_LANGUAGE:CXX>:${SPLINTERCAM_CXX_OPTIONS}>)
  # C wrappers of vendored files (ADR 0009): C99, warnings off for that code only, the strict float
  # flags of D-097, hidden symbols; an empty <sys/time.h> for MSVC from cmake/msvc-shim/. 64-bit
  # targets only (x86-64 SSE2, ARM64), so no x87 extended precision (REQ-G2D-015).
  set_target_properties(splintercam_kernel_code PROPERTIES C_STANDARD 99 C_EXTENSIONS ON
                        C_VISIBILITY_PRESET hidden)
  if(MSVC)
    target_compile_options(splintercam_kernel_code PRIVATE $<$<COMPILE_LANGUAGE:C>:/w /fp:precise>)
    # Not per language: the Visual Studio generators do not take $<COMPILE_LANGUAGE> in include
    # directories of a target that mixes C and C++. Only predicates.c includes <sys/time.h>.
    target_include_directories(splintercam_kernel_code PRIVATE
                               ${PROJECT_SOURCE_DIR}/cmake/msvc-shim)
  else()
    target_compile_options(splintercam_kernel_code PRIVATE
                           $<$<COMPILE_LANGUAGE:C>:-w -ffp-contract=off -fno-fast-math>)
  endif()
  # ASan off for the vendored C code only (pending Peter's approval, plan 0003, step 5): its
  # expansion sums read one element past the end of an input array (predicates.c, enow =
  # e[++eindex] in fast_expansion_sum_zeroelim and its kin) and use that value only while
  # eindex < elen, so results are unaffected, but ASan reports a stack-buffer-overflow in
  # orient2dadapt. The file stays unchanged (ADR 0009); UBSan stays on for it.
  if(SPLINTERCAM_SANITIZE)
    target_compile_options(splintercam_kernel_code PRIVATE
                           $<$<COMPILE_LANGUAGE:C>:-fno-sanitize=address>)
  endif()
  target_link_libraries(splintercam_kernel_code PRIVATE Clipper2)
  target_link_libraries(_kernels PRIVATE splintercam_kernel_code)
endif()

install(TARGETS _kernels LIBRARY DESTINATION splintercam COMPONENT splintercam)

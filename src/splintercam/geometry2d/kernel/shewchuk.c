/* SPDX-License-Identifier: Apache-2.0 */
/* Compiles Shewchuk's predicates.c, vendored unchanged in vendor/ (ADR 0009; D-097). The build
   quirks live here and in CMakeLists.txt, never in the vendored file. */
#if defined(_MSC_VER)
/* MSVC's C library has no random(); only predicates.c's test-data generators call it. */
#define random rand
#endif
#include "vendor/predicates.c"

// SPDX-License-Identifier: Apache-2.0
// The functions of the vendored predicates.c the kernel uses (ADR 0009), with prototypes for its
// old-style definitions. Expansions are arrays of doubles, smallest component first (SRC-032).
#pragma once

extern "C" {
void exactinit();
double orient2d(double* pa, double* pb, double* pc);
double incircle(double* pa, double* pb, double* pc, double* pd);
int fast_expansion_sum_zeroelim(int elen, double* e, int flen, double* f, double* h);
int compress(int elen, double* e, double* h);
}

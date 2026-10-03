// SPDX-License-Identifier: Apache-2.0
// The functions of the vendored predicates.c the kernel uses (ADR 0009), with prototypes for its
// old-style definitions.
#pragma once

extern "C" {
void exactinit();
double orient2d(double* pa, double* pb, double* pc);
double incircle(double* pa, double* pb, double* pc, double* pd);
}

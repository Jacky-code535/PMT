// Copyright 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

package intelpmtreceiver

import (
	"math"
	"testing"
)

func TestEvalPreservesFullWidthUint64IdentityMask(t *testing.T) {
	const raw = uint64(1743184077)
	got, err := eval(
		"( parameter_0 & 0xffffffffffffffff ) / ( 2**26 )",
		map[string]interface{}{"parameter_0": raw},
	)
	if err != nil {
		t.Fatal(err)
	}

	value, ok := got.(float64)
	if !ok {
		t.Fatalf("result type = %T, want float64", got)
	}
	want := float64(raw) / float64(uint64(1)<<26)
	if math.Abs(value-want) > 1e-12 {
		t.Fatalf("result = %.12f, want %.12f", value, want)
	}
}

func TestEvalRetainsNarrowBitMask(t *testing.T) {
	got, err := eval(
		"parameter_0 & 0xff",
		map[string]interface{}{"parameter_0": uint64(0x1234)},
	)
	if err != nil {
		t.Fatal(err)
	}
	if got != float64(0x34) {
		t.Fatalf("result = %#v, want %v", got, float64(0x34))
	}
}

// Copyright 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

package intelpmtreceiver

import "testing"

func TestExpandFIVRHealthMetrics(t *testing.T) {
	const name = "FIVR_HEALTH_MONITOR_0_0.FIVR_HEALTH_MONITOR_0"
	values := map[string]MetricValue{name: {Name: name, Type: "gauge", Value: uint64(0x39)}}

	expandFIVRHealthMetrics(values)

	wants := map[string]uint64{
		name + ".available":            1,
		name + ".status_00":            1,
		name + ".status_01":            2,
		name + ".status_02":            3,
		name + ".status_03":            0,
		name + ".nonzero_status_count": 3,
	}
	for metricName, want := range wants {
		metric, ok := values[metricName]
		if !ok {
			t.Fatalf("missing derived metric %q", metricName)
		}
		if got, ok := metric.Value.(uint64); !ok || got != want {
			t.Errorf("%s = %#v, want %d", metricName, metric.Value, want)
		}
	}
	if got := len(values); got != 35 {
		t.Fatalf("metric count = %d, want 35 (raw + availability + count + 32 statuses)", got)
	}
}

func TestExpandFIVRHealthMetricsSuppressesPoison(t *testing.T) {
	const name = "FIVR_HEALTH_MONITOR_1_1.FIVR_HEALTH_MONITOR_1"
	values := map[string]MetricValue{name: {Name: name, Type: "gauge", Value: uint64(0xdeadbeefdeadbeef)}}

	expandFIVRHealthMetrics(values)

	if _, ok := values[name]; ok {
		t.Fatal("poison raw metric was not suppressed")
	}
	if got := values[name+".available"].Value; got != uint64(0) {
		t.Fatalf("availability = %#v, want 0", got)
	}
	if got := len(values); got != 1 {
		t.Fatalf("metric count = %d, want availability only", got)
	}
}

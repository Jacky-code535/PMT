// Copyright 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// pmt-fallback-debug decodes a saved Redfish PMT response to JSON only. It does
// not construct an OpenTelemetry receiver and has no Prometheus export path.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"

	intelpmtreceiver "github.com/intel/Intel-PMT/tools/otel/intelpmtreceiver"
)

type debugOutput struct {
	SafetyStatus string                                 `json:"safety_status"`
	Source       string                                 `json:"source"`
	Results      []intelpmtreceiver.FallbackDebugResult `json:"results"`
	Errors       []debugError                           `json:"errors,omitempty"`
}

type debugError struct {
	Index        int    `json:"index"`
	GUID         string `json:"guid"`
	ReportedSize uint64 `json:"reported_size_bytes"`
	Error        string `json:"error"`
}

func main() {
	metadataPath := flag.String("metadata", "", "path to pmt.xml metadata")
	inputPath := flag.String("input", "-", "saved Redfish JSON path, or - for stdin")
	flag.Parse()
	if *metadataPath == "" {
		fmt.Fprintln(os.Stderr, "-metadata is required")
		os.Exit(2)
	}

	input, err := readInput(*inputPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var telemetry intelpmtreceiver.RedfishTelemetryData
	if err := json.Unmarshal(input, &telemetry); err != nil {
		fmt.Fprintln(os.Stderr, "parse input JSON:", err)
		os.Exit(1)
	}

	output := debugOutput{
		SafetyStatus: "UNVERIFIED_OFFLINE_DEBUG_ONLY",
		Source:       *inputPath,
		Results:      make([]intelpmtreceiver.FallbackDebugResult, 0, len(telemetry.TelemetryData)),
	}
	guidInstances := make(map[string]int)
	for index, aggregator := range telemetry.TelemetryData {
		result, err := intelpmtreceiver.DebugDecodeWithUniqueGUIDFallback(*metadataPath, aggregator)
		if err != nil {
			output.Errors = append(output.Errors, debugError{
				Index: index, GUID: aggregator.GUID,
				ReportedSize: aggregator.Size, Error: err.Error(),
			})
			continue
		}
		result.RecordIndex = index
		result.GUIDInstanceIndex = guidInstances[result.GUID]
		guidInstances[result.GUID]++
		output.Results = append(output.Results, result)
	}
	if len(output.Errors) == 0 && len(output.Results) > 0 {
		allExact := true
		for _, result := range output.Results {
			if !result.ExactMatch {
				allExact = false
				break
			}
		}
		if allExact {
			output.SafetyStatus = "EXACT_SCHEMA_OFFLINE_VALIDATION"
		}
	}

	encoder := json.NewEncoder(os.Stdout)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(output); err != nil {
		fmt.Fprintln(os.Stderr, "write output JSON:", err)
		os.Exit(1)
	}
	if len(output.Errors) > 0 {
		os.Exit(1)
	}
}

func readInput(path string) ([]byte, error) {
	if path == "-" {
		return io.ReadAll(os.Stdin)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read input: %w", err)
	}
	return data, nil
}

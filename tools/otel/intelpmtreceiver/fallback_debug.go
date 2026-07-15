// Copyright 2026 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package intelpmtreceiver

import (
	"encoding/base64"
	"errors"
	"fmt"
	"path/filepath"
	"sort"
	"strings"

	"go.uber.org/zap"
)

// FallbackDebugMetric is one offline-decoded metric. It is deliberately separate
// from the Collector pipeline and cannot be exported to Prometheus.
type FallbackDebugMetric struct {
	Name        string      `json:"name"`
	Type        string      `json:"type"`
	Value       interface{} `json:"value"`
	Unit        string      `json:"unit,omitempty"`
	Description string      `json:"description,omitempty"`
}

// FallbackDebugResult describes an unverified unique-GUID fallback decode.
type FallbackDebugResult struct {
	SafetyStatus        string                `json:"safety_status"`
	RecordIndex         int                   `json:"record_index"`
	GUIDInstanceIndex   int                   `json:"guid_instance_index"`
	GUID                string                `json:"guid"`
	CollectionTimestamp string                `json:"collection_timestamp"`
	ReportedSizeBytes   uint64                `json:"reported_size_bytes"`
	DecodedDataBytes    uint64                `json:"decoded_data_bytes"`
	CandidateSizeBytes  uint64                `json:"candidate_xml_size_bytes"`
	RequiredBytes       uint64                `json:"candidate_required_bytes"`
	TrailingBytes       uint64                `json:"uninterpreted_trailing_bytes"`
	ExactMatch          bool                  `json:"exact_guid_size_match"`
	UniqueGUIDFallback  bool                  `json:"unique_guid_fallback"`
	XMLBaseDir          string                `json:"xml_base_dir"`
	Warnings            []string              `json:"warnings"`
	MetricCount         int                   `json:"metric_count"`
	KnownPoisonCount    int                   `json:"known_poison_metric_count"`
	Metrics             []FallbackDebugMetric `json:"metrics"`
}

// DebugDecodeWithUniqueGUIDFallback performs an offline-only decode. Exact
// GUID+size matching is preferred. A fallback is allowed only when the GUID has
// exactly one XML candidate and the decoded payload covers every XML offset.
func DebugDecodeWithUniqueGUIDFallback(
	metadataPath string,
	input RedfishMetricAggregator,
) (FallbackDebugResult, error) {
	result := FallbackDebugResult{
		SafetyStatus:        "UNVERIFIED_OFFLINE_DEBUG_ONLY",
		GUID:                strings.ToLower(strings.TrimSpace(input.GUID)),
		CollectionTimestamp: input.CollectionTimestamp,
		ReportedSizeBytes:   input.Size,
	}

	var metadata PMTMetadata
	if err := GetPMTMetadata(metadataPath, &metadata); err != nil {
		return result, fmt.Errorf("load metadata: %w", err)
	}
	lookup, err := BuildLookupMap(metadata, zap.NewNop())
	if err != nil {
		return result, fmt.Errorf("build lookup map: %w", err)
	}

	xmlSet, candidateSize, exact, err := selectDebugXMLSet(lookup, result.GUID, input.Size)
	if err != nil {
		return result, err
	}
	if !exact {
		result.UniqueGUIDFallback = true
		result.Warnings = append(result.Warnings,
			"GUID matched a single XMLSet but Size did not; offsets and semantics are not proven compatible",
		)
	}
	result.ExactMatch = exact
	if exact {
		result.SafetyStatus = "EXACT_SCHEMA_OFFLINE_VALIDATION"
	}
	result.CandidateSizeBytes = candidateSize
	result.XMLBaseDir = xmlSet.Basedir

	decoded, err := base64.StdEncoding.DecodeString(input.Data)
	if err != nil {
		return result, fmt.Errorf("decode Data: %w", err)
	}
	result.DecodedDataBytes = uint64(len(decoded))
	if result.DecodedDataBytes != input.Size {
		return result, fmt.Errorf(
			"reported Size %d differs from decoded Data length %d", input.Size, len(decoded),
		)
	}

	var common DataTypes
	if err := GetPMTCommonDatatypes(filepath.Join(xmlSet.Basedir, xmlSet.Common), &common); err != nil {
		return result, fmt.Errorf("load common datatypes: %w", err)
	}
	dataTypes := make(map[string]DataType, len(common.DataTypes))
	for _, dataType := range common.DataTypes {
		dataTypes[dataType.Name] = dataType
	}

	var aggregator Aggregator
	if err := GetPMTAggregator(filepath.Join(xmlSet.Basedir, xmlSet.Aggregator), &aggregator); err != nil {
		return result, fmt.Errorf("load aggregator XML: %w", err)
	}
	var aggregatorInterface AggregatorInterface
	if err := GetPMTAggregatorInterface(
		filepath.Join(xmlSet.Basedir, xmlSet.AggregatorInterface), &aggregatorInterface,
	); err != nil {
		return result, fmt.Errorf("load aggregator interface XML: %w", err)
	}

	for _, group := range aggregator.SampleGroup {
		for _, sample := range group.Sample {
			required := sample.CalculatedByteOffset + sampleSizeBytes
			if required > result.RequiredBytes {
				result.RequiredBytes = required
			}
		}
	}
	if result.RequiredBytes == 0 {
		return result, errors.New("candidate XML has no decodable samples")
	}
	if result.DecodedDataBytes < result.RequiredBytes {
		return result, fmt.Errorf(
			"decoded payload has %d bytes but candidate XML needs at least %d",
			result.DecodedDataBytes, result.RequiredBytes,
		)
	}
	result.TrailingBytes = result.DecodedDataBytes - result.RequiredBytes
	if result.TrailingBytes > 0 {
		result.Warnings = append(result.Warnings,
			fmt.Sprintf("%d trailing payload bytes are not interpreted by the candidate XML", result.TrailingBytes),
		)
	}

	values := processAggregatorData(input.Data, aggregator, aggregatorInterface, dataTypes, zap.NewNop())
	metricNames := make([]string, 0, len(values))
	for name := range values {
		metricNames = append(metricNames, name)
	}
	sort.Strings(metricNames)
	for _, name := range metricNames {
		value := values[name]
		if isKnownPoisonValue(value.Value) ||
			(strings.HasSuffix(name, ".available") && value.Value == uint64(0)) {
			result.KnownPoisonCount++
		}
		result.Metrics = append(result.Metrics, FallbackDebugMetric{
			Name: value.Name, Type: value.Type, Value: value.Value,
			Unit: value.Unit, Description: value.Description,
		})
	}
	result.MetricCount = len(result.Metrics)
	if result.KnownPoisonCount > 0 {
		result.Warnings = append(result.Warnings, fmt.Sprintf(
			"%d decoded metrics contain known DEADBEEF poison values and are not plausible telemetry",
			result.KnownPoisonCount,
		))
	}
	if len(result.Metrics) == 0 {
		return result, errors.New("candidate XML produced no metrics")
	}
	return result, nil
}

func isKnownPoisonValue(value interface{}) bool {
	const (
		deadBeef32 = uint64(0xdeadbeef)
		deadBeef64 = uint64(0xdeadbeefdeadbeef)
	)
	switch typed := value.(type) {
	case uint64:
		return typed == deadBeef32 || typed == deadBeef64
	case uint32:
		return uint64(typed) == deadBeef32
	case int64:
		return typed >= 0 && (uint64(typed) == deadBeef32 || uint64(typed) == deadBeef64)
	case int:
		return typed >= 0 && uint64(typed) == deadBeef32
	case float64:
		return typed == float64(deadBeef32) || typed == float64(deadBeef64)
	default:
		return false
	}
}

func selectDebugXMLSet(
	lookup PMTLookupMap,
	guid string,
	size uint64,
) (XMLSet, uint64, bool, error) {
	exactKey := PMTAggKey{GUID: guid, Size: size}
	if xmlSet, ok := lookup[exactKey]; ok {
		return xmlSet, size, true, nil
	}

	keys := make([]PMTAggKey, 0, 1)
	for key := range lookup {
		if key.GUID == guid {
			keys = append(keys, key)
		}
	}
	if len(keys) != 1 {
		return XMLSet{}, 0, false, fmt.Errorf(
			"exact GUID+size match failed and GUID has %d XML candidates", len(keys),
		)
	}
	return lookup[keys[0]], keys[0].Size, false, nil
}

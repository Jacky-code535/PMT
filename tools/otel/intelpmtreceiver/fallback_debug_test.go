// Copyright 2025 Intel Corporation
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

import "testing"

func TestSelectDebugXMLSetExactMatch(t *testing.T) {
	want := XMLSet{Basedir: "exact"}
	lookup := PMTLookupMap{
		{GUID: "0x1", Size: 16}: want,
		{GUID: "0x1", Size: 32}: {Basedir: "other"},
	}

	got, size, exact, err := selectDebugXMLSet(lookup, "0x1", 16)
	if err != nil || !exact || size != 16 || got.Basedir != want.Basedir {
		t.Fatalf("got set=%+v size=%d exact=%v err=%v", got, size, exact, err)
	}
}

func TestSelectDebugXMLSetUniqueGUIDFallback(t *testing.T) {
	lookup := PMTLookupMap{{GUID: "0x1", Size: 16}: {Basedir: "candidate"}}

	got, size, exact, err := selectDebugXMLSet(lookup, "0x1", 64)
	if err != nil || exact || size != 16 || got.Basedir != "candidate" {
		t.Fatalf("got set=%+v size=%d exact=%v err=%v", got, size, exact, err)
	}
}

func TestSelectDebugXMLSetRejectsAmbiguousOrMissingGUID(t *testing.T) {
	lookup := PMTLookupMap{
		{GUID: "0x1", Size: 16}: {Basedir: "first"},
		{GUID: "0x1", Size: 32}: {Basedir: "second"},
	}

	for _, guid := range []string{"0x1", "0x2"} {
		if _, _, _, err := selectDebugXMLSet(lookup, guid, 64); err == nil {
			t.Fatalf("expected GUID %s to be rejected", guid)
		}
	}
}

func TestIsKnownPoisonValue(t *testing.T) {
	for _, value := range []interface{}{
		uint32(0xdeadbeef), uint64(0xdeadbeef), uint64(0xdeadbeefdeadbeef),
		int64(0xdeadbeef), float64(0xdeadbeef),
	} {
		if !isKnownPoisonValue(value) {
			t.Fatalf("expected %T(%v) to be poison", value, value)
		}
	}
	for _, value := range []interface{}{uint64(0), uint64(4792), -1, "0xdeadbeef"} {
		if isKnownPoisonValue(value) {
			t.Fatalf("did not expect %T(%v) to be poison", value, value)
		}
	}
}

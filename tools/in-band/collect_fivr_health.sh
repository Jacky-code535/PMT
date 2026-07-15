#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Atomically publish one in-band GNR FIVR Health snapshot as JSON Lines.

set -eu

reader=${PMT_READER:-/usr/local/bin/read_pmt_metric}
output=${PMT_OUTPUT:-/var/lib/intel-pmt/fivr-health.jsonl}
root=${PMT_SYSFS_ROOT:-/sys/class/intel_pmt}
output_dir=$(dirname "$output")

umask 027
mkdir -p "$output_dir"
temporary=$(mktemp "$output_dir/.fivr-health.XXXXXX")
trap 'rm -f "$temporary"' EXIT HUP INT TERM

"$reader" --fivr --root "$root" > "$temporary"
chmod 0640 "$temporary"
mv -f "$temporary" "$output"
trap - EXIT HUP INT TERM

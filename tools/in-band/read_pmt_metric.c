// SPDX-License-Identifier: Apache-2.0
// Read Intel PMT metrics directly from the Linux in-band sysfs interface.

#define _POSIX_C_SOURCE 200809L

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/types.h>
#include <unistd.h>

#define SYSFS_ROOT "/sys/class/intel_pmt"
#define TEXT_SIZE 128

struct metric_request {
    const char *guid;
    uint64_t expected_size;
    uint64_t offset;
    size_t width;
    const char *name;
    bool decode_two_bit;
    bool allow_larger_size;
};

static const struct metric_request fivr_requests[] = {
    {"0x22806802", 6784, 1440, 8, "FIVR_HEALTH_MONITOR_0", true, false},
    {"0x22806802", 6784, 1448, 8, "FIVR_HEALTH_MONITOR_1", true, false},
    {"0x22806802", 6784, 1456, 8, "FIVR_HEALTH_MONITOR_2", true, false},
    {"0x22491753", 6272, 32, 8, "FIVR_HEALTH_MONITOR_0", true, false},
    {"0x22491753", 6272, 40, 8, "FIVR_HEALTH_MONITOR_1", true, false},
    {"0x22491753", 6272, 48, 8, "FIVR_HEALTH_MONITOR_2", true, false},
};

static void usage(const char *program)
{
    fprintf(stderr,
            "Usage:\n"
            "  %s --fivr [--root PATH]\n"
            "  %s --guid GUID --offset BYTES [--width 1|2|4|8]\n"
            "     [--expected-size BYTES | --minimum-size BYTES]\n"
            "     [--name NAME] [--decode-2bit]\n"
            "     [--root PATH]\n\n"
            "Output is one JSON object per matching telemetry device/metric.\n",
            program, program);
}

static int read_text(const char *path, char *buffer, size_t capacity)
{
    FILE *file = fopen(path, "r");
    if (file == NULL)
        return -1;
    if (fgets(buffer, (int)capacity, file) == NULL) {
        fclose(file);
        return -1;
    }
    fclose(file);
    buffer[strcspn(buffer, "\r\n")] = '\0';
    return 0;
}

static int parse_u64(const char *text, uint64_t *value)
{
    char *end = NULL;
    unsigned long long parsed;

    errno = 0;
    parsed = strtoull(text, &end, 0);
    if (errno != 0 || end == text || *end != '\0')
        return -1;
    *value = (uint64_t)parsed;
    return 0;
}

static int normalize_guid(const char *text, char output[11])
{
    uint64_t value;
    if (parse_u64(text, &value) != 0 || value > UINT32_MAX)
        return -1;
    snprintf(output, 11, "0x%08" PRIx64, value);
    return 0;
}

static int read_value(const char *path, uint64_t offset, size_t width,
                      uint64_t *value)
{
    uint8_t bytes[8] = {0};
    int fd = open(path, O_RDONLY);
    if (fd < 0)
        return -1;

    ssize_t count = pread(fd, bytes, width, (off_t)offset);
    int saved_errno = errno;
    close(fd);
    errno = saved_errno;
    if (count != (ssize_t)width) {
        if (count >= 0)
            errno = EIO;
        return -1;
    }

    *value = 0;
    for (size_t index = 0; index < width; ++index)
        *value |= (uint64_t)bytes[index] << (index * 8);
    return 0;
}

static void print_result(const char *device, const char *telem_path,
                         const struct metric_request *request, uint64_t size,
                         uint64_t value)
{
    bool poison = value == UINT64_C(0xdeadbeef) ||
                  value == UINT64_C(0xdeadbeefdeadbeef);
    const char *layout = request->expected_size == 0 ? "unchecked" :
                         (size == request->expected_size ?
                          "exact" : "compatible_prefix_unverified");

    printf("{\"device\":\"%s\",\"telem\":\"%s\",\"guid\":\"%s\","
           "\"size_bytes\":%" PRIu64 ",\"schema_size_bytes\":%" PRIu64 ","
           "\"layout_status\":\"%s\",\"metric\":\"%s\","
           "\"offset_bytes\":%" PRIu64 ",\"width_bytes\":%zu,"
           "\"available\":%s,\"value_u64\":%" PRIu64 ","
           "\"value_hex\":\"0x%0*" PRIx64 "\"",
           device, telem_path, request->guid, size, request->expected_size,
           layout, request->name,
           request->offset, request->width, poison ? "false" : "true", value,
           (int)(request->width * 2), value);

    if (request->decode_two_bit && !poison) {
        printf(",\"two_bit_codes\":[");
        for (size_t field = 0; field < request->width * 4; ++field) {
            if (field != 0)
                putchar(',');
            printf("%" PRIu64, (value >> (field * 2)) & UINT64_C(3));
        }
        putchar(']');
    }
    puts("}");
}

static int collect_request(const char *root,
                           const struct metric_request *request)
{
    DIR *directory = opendir(root);
    struct dirent *entry;
    char wanted_guid[11];
    int matches = 0;

    if (directory == NULL) {
        fprintf(stderr, "cannot open %s: %s\n", root, strerror(errno));
        return -1;
    }
    if (normalize_guid(request->guid, wanted_guid) != 0) {
        fprintf(stderr, "invalid GUID: %s\n", request->guid);
        closedir(directory);
        return -1;
    }

    while ((entry = readdir(directory)) != NULL) {
        char guid_path[PATH_MAX], size_path[PATH_MAX], telem_path[PATH_MAX];
        char guid_text[TEXT_SIZE], actual_guid[11], size_text[TEXT_SIZE];
        uint64_t size, value;

        if (strncmp(entry->d_name, "telem", 5) != 0)
            continue;
        snprintf(guid_path, sizeof(guid_path), "%s/%s/guid", root, entry->d_name);
        if (read_text(guid_path, guid_text, sizeof(guid_text)) != 0 ||
            normalize_guid(guid_text, actual_guid) != 0 ||
            strcasecmp(actual_guid, wanted_guid) != 0)
            continue;

        snprintf(size_path, sizeof(size_path), "%s/%s/size", root, entry->d_name);
        if (read_text(size_path, size_text, sizeof(size_text)) != 0 ||
            parse_u64(size_text, &size) != 0) {
            fprintf(stderr, "%s: cannot parse size\n", entry->d_name);
            continue;
        }
        if (request->expected_size != 0 &&
            ((!request->allow_larger_size && size != request->expected_size) ||
             (request->allow_larger_size && size < request->expected_size))) {
            fprintf(stderr,
                    "%s: GUID %s size mismatch: got %" PRIu64
                    ", %s %" PRIu64 "; skipped\n",
                    entry->d_name, actual_guid, size,
                    request->allow_larger_size ? "minimum" : "expected",
                    request->expected_size);
            continue;
        }
        if (request->offset > size || request->width > size - request->offset) {
            fprintf(stderr, "%s: read [%" PRIu64 ", %" PRIu64
                            ") exceeds telemetry size %" PRIu64 "; skipped\n",
                    entry->d_name, request->offset,
                    request->offset + request->width, size);
            continue;
        }

        snprintf(telem_path, sizeof(telem_path), "%s/%s/telem", root, entry->d_name);
        if (read_value(telem_path, request->offset, request->width, &value) != 0) {
            fprintf(stderr, "%s: read failed: %s\n", telem_path, strerror(errno));
            continue;
        }
        print_result(entry->d_name, telem_path, request, size, value);
        ++matches;
    }
    closedir(directory);
    return matches;
}

int main(int argc, char **argv)
{
    const char *root = SYSFS_ROOT;
    struct metric_request request = {0};
    bool fivr = false;

    request.width = 8;
    request.name = "raw_metric";
    for (int index = 1; index < argc; ++index) {
        if (strcmp(argv[index], "--fivr") == 0) {
            fivr = true;
        } else if (strcmp(argv[index], "--decode-2bit") == 0) {
            request.decode_two_bit = true;
        } else if (index + 1 < argc && strcmp(argv[index], "--root") == 0) {
            root = argv[++index];
        } else if (index + 1 < argc && strcmp(argv[index], "--guid") == 0) {
            request.guid = argv[++index];
        } else if (index + 1 < argc && strcmp(argv[index], "--offset") == 0) {
            if (parse_u64(argv[++index], &request.offset) != 0) {
                usage(argv[0]);
                return EXIT_FAILURE;
            }
        } else if (index + 1 < argc && strcmp(argv[index], "--expected-size") == 0) {
            if (parse_u64(argv[++index], &request.expected_size) != 0) {
                usage(argv[0]);
                return EXIT_FAILURE;
            }
            request.allow_larger_size = false;
        } else if (index + 1 < argc && strcmp(argv[index], "--minimum-size") == 0) {
            if (parse_u64(argv[++index], &request.expected_size) != 0) {
                usage(argv[0]);
                return EXIT_FAILURE;
            }
            request.allow_larger_size = true;
        } else if (index + 1 < argc && strcmp(argv[index], "--width") == 0) {
            uint64_t width;
            if (parse_u64(argv[++index], &width) != 0 ||
                (width != 1 && width != 2 && width != 4 && width != 8)) {
                usage(argv[0]);
                return EXIT_FAILURE;
            }
            request.width = (size_t)width;
        } else if (index + 1 < argc && strcmp(argv[index], "--name") == 0) {
            request.name = argv[++index];
        } else {
            usage(argv[0]);
            return EXIT_FAILURE;
        }
    }

    int total = 0;
    if (fivr) {
        for (size_t index = 0;
             index < sizeof(fivr_requests) / sizeof(fivr_requests[0]); ++index) {
            int count = collect_request(root, &fivr_requests[index]);
            if (count < 0)
                return EXIT_FAILURE;
            total += count;
        }
    } else {
        if (request.guid == NULL) {
            usage(argv[0]);
            return EXIT_FAILURE;
        }
        int count = collect_request(root, &request);
        if (count < 0)
            return EXIT_FAILURE;
        total = count;
    }

    if (total == 0) {
        fprintf(stderr, "no matching readable telemetry metrics found\n");
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}

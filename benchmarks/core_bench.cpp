// AXOVAR G5 in-process microbenchmark for the exact G0/G1 replay code.
// No third-party dependency or simulated latency claim from subprocess startup.
// The monolithic core is included intentionally until its public API is extracted.
#define AXOVAR_NO_MAIN
#include "../core/main.cpp"

#include <chrono>
#include <functional>
#include <numeric>

namespace {

std::uint64_t fingerprint(const std::string& output) {
    std::uint64_t digest = UINT64_C(14695981039346656037);
    for (unsigned char byte : output) {
        digest ^= byte;
        digest *= UINT64_C(1099511628211);
    }
    return digest;
}

std::uint64_t fingerprint_events(const std::vector<axovar::Event>& events) {
    std::uint64_t digest = UINT64_C(14695981039346656037);
    for (const auto& event : events) {
        // Hash raw input records to avoid incorrectly optimizing the load away.
        digest ^= fingerprint(event.raw);
        digest *= UINT64_C(1099511628211);
    }
    return digest;
}

std::int64_t percentile(const std::vector<std::int64_t>& sorted, std::size_t percent) {
    const auto rank = (sorted.size() * percent + 99) / 100;
    return sorted.at(std::max<std::size_t>(1, rank) - 1);
}

void benchmark(const std::string& fixture, const std::string& mode,
               int warmups, int samples, std::size_t step) {
    const auto data = axovar::load(fixture);
    const auto clamped = std::min(step, data.size());
    const auto baseline = mode == "ingest" ? fingerprint_events(data)
                                          : fingerprint(axovar::json(data, clamped, "benchmark.csv"));
    std::vector<std::int64_t> durations;
    durations.reserve(static_cast<std::size_t>(samples));
    using clock = std::chrono::steady_clock;
    for (int n = -warmups; n < samples; ++n) {
        const auto start = clock::now();
        std::uint64_t checksum{};
        if (mode == "ingest") {
            const auto records = axovar::load(fixture);
            checksum = fingerprint_events(records);
        } else if (mode == "replay") {
            const auto state = axovar::json(data, clamped, "benchmark.csv");
            checksum = fingerprint(state);
        } else {
            throw std::runtime_error("mode must be ingest or replay");
        }
        const auto end = clock::now();
        if (checksum != baseline)
            throw std::runtime_error("output mismatch during benchmark");
        if (n >= 0) {
            const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
            durations.push_back(elapsed);
        }
    }
    std::sort(durations.begin(), durations.end());
    const auto sum = std::accumulate(durations.begin(), durations.end(), std::int64_t{0});
    std::ostringstream result;
    result << "{\"schema\":\"AXV-PERF-001\",\"benchmark\":\"" << mode
           << "\",\"synthetic\":true,\"unit\":\"ns\",\"event_count\":" << data.size()
           << ",\"replay_step\":" << clamped << ",\"warmups\":" << warmups
           << ",\"samples\":" << samples
           << ",\"min_ns\":" << durations.front()
           << ",\"p50_ns\":" << percentile(durations, 50)
           << ",\"p95_ns\":" << percentile(durations, 95)
           << ",\"p99_ns\":" << percentile(durations, 99)
           << ",\"max_ns\":" << durations.back()
           << ",\"mean_ns\":" << (sum / samples)
           << ",\"checksum\":\"" << std::hex << baseline << "\""
           << ",\"scope\":\"in_process_fixture_ingest_or_replay\"}";
    std::cout << result.str() << '\n';
}

} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 6) {
            std::cerr << "Usage: axovar_bench MODE FILE STEP WARMUPS SAMPLES\n";
            return 2;
        }
        const std::string mode = argv[1];
        if (mode != "ingest" && mode != "replay")
            throw std::runtime_error("unrecognized benchmark mode");
        const auto step = axovar::integer(argv[3], "step");
        const auto warmups = axovar::integer(argv[4], "warmups");
        const auto samples = axovar::integer(argv[5], "samples");
        if (step < 0 || step > 256 || warmups < 1 || warmups > 500 ||
            samples < 5 || samples > 10000)
            throw std::runtime_error("benchmark arguments out of bounds");
        benchmark(argv[2], mode, static_cast<int>(warmups), static_cast<int>(samples),
                  static_cast<std::size_t>(step));
    } catch (const std::exception& exc) {
        std::cerr << "AXOVAR benchmark error: " << exc.what() << '\n';
        return 1;
    }
}
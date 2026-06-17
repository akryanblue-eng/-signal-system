// Deterministic test for the engine-side resample cache.
//
// Verifies: the SHA-256 implementation matches a known test vector (so the
// cache key itself is trustworthy), a first import is a cache miss that
// produces correct resampled output, a repeat import of the same content is
// a cache hit returning bit-identical data, and different content produces a
// different cache entry rather than colliding.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <iostream>
#include <vector>

#include "AssetManager.h"
#include "Sha256.h"

namespace {

constexpr double PI = 3.14159265358979323846;

std::vector<float> makeSine(double freqHz, double rate, std::size_t numSamples) {
    std::vector<float> out(numSamples);
    for (std::size_t i = 0; i < numSamples; ++i) {
        out[i] = static_cast<float>(std::sin(2.0 * PI * freqHz * static_cast<double>(i) / rate));
    }
    return out;
}

} // namespace

bool runAssetManagerTest() {
    // 1. SHA-256 known test vector: sha256("abc")
    const std::string abcHash = chilli::sha256Hex(reinterpret_cast<const uint8_t*>("abc"), 3);
    const bool shaCorrect =
        abcHash == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

    const std::filesystem::path cacheDir =
        std::filesystem::temp_directory_path() / "chilli_asset_manager_test_cache";
    std::filesystem::remove_all(cacheDir); // start from a clean slate

    constexpr double SRC_RATE = 48000.0;
    constexpr double DST_RATE = 44100.0;
    auto sampleA = makeSine(440.0, SRC_RATE, 2048);
    auto sampleB = makeSine(880.0, SRC_RATE, 2048); // different content -> different cache entry

    chilli::AssetManager mgr(cacheDir);

    bool firstHit = true;
    auto bufA1 = mgr.getOrResample(sampleA, SRC_RATE, DST_RATE, &firstHit);
    const bool firstWasMiss = !firstHit;
    const bool cacheFileCreated = std::filesystem::exists(mgr.cachePath(sampleA, SRC_RATE, DST_RATE));

    bool secondHit = false;
    auto bufA2 = mgr.getOrResample(sampleA, SRC_RATE, DST_RATE, &secondHit);
    const bool secondWasHit = secondHit;
    const bool identicalData =
        bufA1.samples.size() == bufA2.samples.size() && bufA1.sampleRate == bufA2.sampleRate &&
        std::equal(bufA1.samples.begin(), bufA1.samples.end(), bufA2.samples.begin());

    bool thirdHit = true;
    auto bufB = mgr.getOrResample(sampleB, SRC_RATE, DST_RATE, &thirdHit);
    const bool differentContentMisses = !thirdHit;
    const bool differentCacheEntry =
        mgr.cachePath(sampleA, SRC_RATE, DST_RATE) != mgr.cachePath(sampleB, SRC_RATE, DST_RATE);
    const bool resampledNonEmpty = !bufB.samples.empty() && bufB.sampleRate == DST_RATE;

    std::filesystem::remove_all(cacheDir); // leave no residue for the next run

    std::cout << "AssetManager Test Results:\n";
    std::cout << "  SHA-256 known vector match:     " << (shaCorrect ? "PASS" : "FAIL") << "\n";
    std::cout << "  First import is a cache miss:   " << (firstWasMiss ? "PASS" : "FAIL") << "\n";
    std::cout << "  Cache file written to disk:     " << (cacheFileCreated ? "PASS" : "FAIL") << "\n";
    std::cout << "  Repeat import is a cache hit:   " << (secondWasHit ? "PASS" : "FAIL") << "\n";
    std::cout << "  Cache hit returns identical data: " << (identicalData ? "PASS" : "FAIL") << "\n";
    std::cout << "  Different content is a cache miss: " << (differentContentMisses ? "PASS" : "FAIL") << "\n";
    std::cout << "  Different content -> different key: " << (differentCacheEntry ? "PASS" : "FAIL") << "\n";
    std::cout << "  Resampled output is well-formed: " << (resampledNonEmpty ? "PASS" : "FAIL") << "\n";

    return shaCorrect && firstWasMiss && cacheFileCreated && secondWasHit && identicalData &&
           differentContentMisses && differentCacheEntry && resampledNonEmpty;
}

int main() {
    const bool ok = runAssetManagerTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}

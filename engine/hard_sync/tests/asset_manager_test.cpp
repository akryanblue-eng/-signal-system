// Deterministic test for the engine-side resample cache.
//
// Verifies: the SHA-256 implementation matches a known test vector (so the
// cache key itself is trustworthy), a first import is a cache miss that
// produces correct resampled output, a repeat import of the same content is
// a cache hit returning bit-identical data, and different content produces a
// different cache entry rather than colliding.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <vector>

#include "AssetManager.h"
#include "Sha256.h"
#include "WavDecoder.h"

namespace {

constexpr double PI = 3.14159265358979323846;

std::vector<float> makeSine(double freqHz, double rate, std::size_t numSamples) {
    std::vector<float> out(numSamples);
    for (std::size_t i = 0; i < numSamples; ++i) {
        out[i] = static_cast<float>(std::sin(2.0 * PI * freqHz * static_cast<double>(i) / rate));
    }
    return out;
}

void appendU32LE(std::vector<uint8_t>& out, uint32_t v) {
    out.push_back(static_cast<uint8_t>(v & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 16) & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 24) & 0xFF));
}
void appendU16LE(std::vector<uint8_t>& out, uint16_t v) {
    out.push_back(static_cast<uint8_t>(v & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
}
void appendTag(std::vector<uint8_t>& out, const char* tag) { out.insert(out.end(), tag, tag + 4); }

// Builds a minimal canonical 16-bit mono PCM WAV byte buffer for the
// path-based getOrResample test below -- mirrors the helper in
// wav_decoder_test.cpp, kept local since each test file here is
// self-contained with no shared fixture file.
std::vector<uint8_t> buildMonoWav16(uint32_t sampleRate, const std::vector<int16_t>& samples) {
    std::vector<uint8_t> pcm;
    for (int16_t s : samples) {
        pcm.push_back(static_cast<uint8_t>(s & 0xFF));
        pcm.push_back(static_cast<uint8_t>((s >> 8) & 0xFF));
    }

    std::vector<uint8_t> fmtChunk;
    appendU16LE(fmtChunk, 1); // PCM integer
    appendU16LE(fmtChunk, 1); // mono
    appendU32LE(fmtChunk, sampleRate);
    appendU32LE(fmtChunk, sampleRate * 2); // byte rate
    appendU16LE(fmtChunk, 2);              // block align
    appendU16LE(fmtChunk, 16);             // bits per sample

    std::vector<uint8_t> body;
    appendTag(body, "WAVE");
    appendTag(body, "fmt ");
    appendU32LE(body, static_cast<uint32_t>(fmtChunk.size()));
    body.insert(body.end(), fmtChunk.begin(), fmtChunk.end());
    appendTag(body, "data");
    appendU32LE(body, static_cast<uint32_t>(pcm.size()));
    body.insert(body.end(), pcm.begin(), pcm.end());

    std::vector<uint8_t> out;
    appendTag(out, "RIFF");
    appendU32LE(out, static_cast<uint32_t>(body.size()));
    out.insert(out.end(), body.begin(), body.end());
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

    // Path-based getOrResample: a thin wrapper that decodes the file and
    // defers to the buffer-based overload above for cache lookup/resample.
    // Since the cache key is a hash of the decoded PCM (not the path), the
    // same content reached via a file path and via decodeWavFile() directly
    // must land in the exact same cache entry.
    constexpr uint32_t WAV_RATE = 48000;
    const std::vector<int16_t> rawSamples = {0, 1000, -1000, 32767, -32768, 500};
    const auto wavBytes = buildMonoWav16(WAV_RATE, rawSamples);
    const auto wavPath = std::filesystem::temp_directory_path() / "chilli_asset_manager_test.wav";
    {
        std::ofstream out(wavPath, std::ios::binary);
        out.write(reinterpret_cast<const char*>(wavBytes.data()),
                   static_cast<std::streamsize>(wavBytes.size()));
    }

    bool pathFirstHit = true;
    const auto pathResult = mgr.getOrResample(wavPath, DST_RATE, &pathFirstHit);
    const bool pathDecodeSucceeded = pathResult.has_value();
    const bool pathFirstWasMiss = !pathFirstHit;

    const auto decodedFromPath = chilli::decodeWavFile(wavPath);
    bool vectorHitAfterPath = false;
    const auto vectorResult = decodedFromPath
        ? mgr.getOrResample(decodedFromPath->samples, decodedFromPath->sampleRate, DST_RATE, &vectorHitAfterPath)
        : chilli::SampleBuffer{};
    const bool sameCacheEntryAsVectorPath = vectorHitAfterPath;
    const bool pathAndVectorIdentical = pathDecodeSucceeded && decodedFromPath.has_value() &&
        pathResult->samples.size() == vectorResult.samples.size() &&
        pathResult->sampleRate == vectorResult.sampleRate &&
        std::equal(pathResult->samples.begin(), pathResult->samples.end(), vectorResult.samples.begin());

    const bool missingFileReturnsNullopt =
        !mgr.getOrResample(wavPath.string() + "_does_not_exist", DST_RATE).has_value();

    std::filesystem::remove(wavPath);
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
    std::cout << "  Path-based import decodes successfully: " << (pathDecodeSucceeded ? "PASS" : "FAIL") << "\n";
    std::cout << "  Path-based import is a cache miss:   " << (pathFirstWasMiss ? "PASS" : "FAIL") << "\n";
    std::cout << "  Same content via vector overload hits path's cache entry: "
              << (sameCacheEntryAsVectorPath ? "PASS" : "FAIL") << "\n";
    std::cout << "  Path-based and vector-based results are bit-identical: "
              << (pathAndVectorIdentical ? "PASS" : "FAIL") << "\n";
    std::cout << "  Missing file returns std::nullopt: " << (missingFileReturnsNullopt ? "PASS" : "FAIL") << "\n";

    return shaCorrect && firstWasMiss && cacheFileCreated && secondWasHit && identicalData &&
           differentContentMisses && differentCacheEntry && resampledNonEmpty && pathDecodeSucceeded &&
           pathFirstWasMiss && sameCacheEntryAsVectorPath && pathAndVectorIdentical && missingFileReturnsNullopt;
}

int main() {
    const bool ok = runAssetManagerTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}

#pragma once

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <optional>
#include <sstream>
#include <vector>

#include "SampleBuffer.h"
#include "Sha256.h"
#include "WavDecoder.h"

namespace chilli {

// Engine-side, platform-agnostic cache for imported samples. The expensive
// part of import is the offline resample (Resampler.h), so this caches the
// *already-resampled* canonical buffer, keyed by a content hash of the
// decoded PCM plus the source/target rates -- not by file path, so moving or
// renaming a source file is still a cache hit.
//
// Where the cache directory lives (app support folder, Files-app-backed
// folder, etc.) is a platform decision left to the caller; this class only
// needs a writable directory.
class AssetManager {
public:
    explicit AssetManager(std::filesystem::path cacheDir) : cacheDir_(std::move(cacheDir)) {
        std::filesystem::create_directories(cacheDir_);
    }

    // decoded: raw PCM at sourceRate, already decoded from whatever file format
    // (WAV/AIFF/etc. decoding happens before this call, not inside it).
    SampleBuffer getOrResample(const std::vector<float>& decoded, double sourceRate,
                                double engineSampleRate, bool* outWasCacheHit = nullptr) {
        const std::filesystem::path path = cachePath(decoded, sourceRate, engineSampleRate);

        if (auto cached = readCache(path)) {
            if (outWasCacheHit) *outWasCacheHit = true;
            return *cached;
        }

        SampleBuffer buf = SampleBuffer::fromDecodedPCM(decoded, sourceRate, engineSampleRate);
        writeCache(path, buf);
        if (outWasCacheHit) *outWasCacheHit = false;
        return buf;
    }

    // Thin wrapper: decode the file, then defer to the buffer-based overload
    // above for the actual cache lookup/resample. No separate path-keyed
    // cache entry exists -- the key is still a hash of the decoded PCM, so a
    // file decoded by path and the same bytes passed directly as a vector
    // land in the same cache entry. Returns std::nullopt if decodeWavFile
    // fails (missing file, bad RIFF magic, unsupported format), preserving
    // the decoder's error signal rather than substituting an empty buffer.
    std::optional<SampleBuffer> getOrResample(const std::filesystem::path& filePath,
                                               double engineSampleRate, bool* outWasCacheHit = nullptr) {
        const auto decoded = decodeWavFile(filePath);
        if (!decoded) return std::nullopt;
        return getOrResample(decoded->samples, decoded->sampleRate, engineSampleRate, outWasCacheHit);
    }

    std::filesystem::path cachePath(const std::vector<float>& decoded, double sourceRate,
                                     double engineSampleRate) const {
        std::ostringstream name;
        name << sha256Hex(decoded) << '_' << static_cast<uint64_t>(sourceRate) << '_'
             << static_cast<uint64_t>(engineSampleRate) << ".pcmcache";
        return cacheDir_ / name.str();
    }

private:
    static constexpr uint32_t kMagic = 0x494c4843; // "CHLI" little-endian

    static std::optional<SampleBuffer> readCache(const std::filesystem::path& path) {
        std::ifstream in(path, std::ios::binary);
        if (!in) return std::nullopt;

        uint32_t magic = 0;
        double rate = 0.0;
        uint64_t count = 0;
        in.read(reinterpret_cast<char*>(&magic), sizeof(magic));
        in.read(reinterpret_cast<char*>(&rate), sizeof(rate));
        in.read(reinterpret_cast<char*>(&count), sizeof(count));
        if (!in || magic != kMagic) return std::nullopt;

        SampleBuffer buf;
        buf.sampleRate = rate;
        buf.samples.resize(static_cast<std::size_t>(count));
        in.read(reinterpret_cast<char*>(buf.samples.data()),
                static_cast<std::streamsize>(count * sizeof(float)));
        if (!in) return std::nullopt;
        return buf;
    }

    static void writeCache(const std::filesystem::path& path, const SampleBuffer& buf) {
        std::ofstream out(path, std::ios::binary | std::ios::trunc);
        if (!out) return;
        const uint64_t count = buf.samples.size();
        out.write(reinterpret_cast<const char*>(&kMagic), sizeof(kMagic));
        out.write(reinterpret_cast<const char*>(&buf.sampleRate), sizeof(buf.sampleRate));
        out.write(reinterpret_cast<const char*>(&count), sizeof(count));
        out.write(reinterpret_cast<const char*>(buf.samples.data()),
                  static_cast<std::streamsize>(count * sizeof(float)));
    }

    std::filesystem::path cacheDir_;
};

} // namespace chilli

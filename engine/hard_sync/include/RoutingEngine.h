#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <vector>

namespace chilli {

// A bus is a pre-allocated accumulation buffer plus a gain. Voices write into
// a bus via accumulate(); the bus never allocates after construction, so it's
// safe to call from the audio thread.
struct Bus {
    std::vector<float> buffer;
    float gain = 1.0f;

    void resize(std::size_t numFrames) { buffer.assign(numFrames, 0.0f); }
    void clear() { std::fill(buffer.begin(), buffer.end(), 0.0f); }

    // Accumulates in source order. For the bus sum to be reproducible across
    // callbacks, callers must trigger voices in a fixed order every time
    // (e.g. the voice pool's natural index order) -- this function does not
    // itself impose an order across multiple calls, it just appends in time.
    //
    // offset lets a caller write a sub-range of the block (e.g. one segment
    // between two mid-block triggers) without smearing it across the whole
    // buffer; it defaults to 0 so every whole-block caller is unaffected.
    void accumulate(const float* source, std::size_t numFrames, std::size_t offset = 0) {
        if (offset >= buffer.size()) return;
        const std::size_t n = std::min(numFrames, buffer.size() - offset);
        for (std::size_t i = 0; i < n; ++i) {
            buffer[offset + i] += source[i];
        }
    }
};

// Fixed-size DAG: NumBuses pre-allocated buses summed, in increasing bus
// index order, into a single main output every block. The bus count and
// block size are both fixed at construction so process() never allocates.
template <std::size_t NumBuses>
class RoutingEngine {
public:
    explicit RoutingEngine(std::size_t blockSize) : blockSize_(blockSize) {
        for (auto& b : buses_) b.resize(blockSize_);
        mainOut_.assign(blockSize_, 0.0f);
    }

    Bus& bus(std::size_t index) { return buses_[index]; }
    const Bus& bus(std::size_t index) const { return buses_[index]; }

    void clearBuses() {
        for (auto& b : buses_) b.clear();
    }

    // Sums every bus, scaled by its gain, into mainOut -- always in increasing
    // bus-index order, so identical bus contents always produce a bit-identical
    // main output regardless of how/when those contents were written.
    void process() {
        std::fill(mainOut_.begin(), mainOut_.end(), 0.0f);
        for (std::size_t b = 0; b < NumBuses; ++b) {
            const auto& buf = buses_[b].buffer;
            const float gain = buses_[b].gain;
            for (std::size_t i = 0; i < blockSize_; ++i) {
                mainOut_[i] += buf[i] * gain;
            }
        }
    }

    const std::vector<float>& mainOut() const { return mainOut_; }
    std::size_t blockSize() const { return blockSize_; }
    static constexpr std::size_t numBuses() { return NumBuses; }

private:
    std::array<Bus, NumBuses> buses_;
    std::vector<float> mainOut_;
    std::size_t blockSize_;
};

} // namespace chilli

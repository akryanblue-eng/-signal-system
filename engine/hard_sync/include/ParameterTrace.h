#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>

// Fixed-capacity, allocation-free circular log of arbitrary Entry records,
// oldest overwritten first once full. A standalone observer, not a
// dependency of whatever it's logging: callers (e.g. ChilliPluginWrapper)
// push their own already-assembled Entry into record() after the event
// they care about has already happened (e.g. right after a
// ParameterBridge::publish() call), rather than this class hooking into
// that event itself. That keeps the thing being observed (ParameterBridge)
// free of any awareness that observation is happening, the same
// correctness-path/observability-path separation this engine already
// draws between MasterBus and whatever might one day meter its output.
//
// Single-writer, same thread that calls record() reads back via
// totalRecorded()/size()/at() in every caller this engine has today; the
// atomic write-count only buys torn-read safety for record() racing a
// concurrent reader of totalRecorded(), not a second concurrent writer
// (same single-writer contract as ParameterBridge, see ParameterBridge.h).
template <typename Entry, std::size_t Capacity = 1024>
class ParameterTrace {
public:
    void record(const Entry& entry) {
        const std::size_t seq = writeCount_.fetch_add(1, std::memory_order_relaxed);
        entries_[seq % Capacity] = entry;
    }

    // Every record() call ever made, including ones already evicted from
    // the ring -- a forensic count, not a size.
    std::size_t totalRecorded() const { return writeCount_.load(std::memory_order_relaxed); }

    // Number of entries currently held, capped at Capacity once the ring
    // has wrapped.
    std::size_t size() const { return std::min<std::size_t>(totalRecorded(), Capacity); }

    // logicalIndex 0 is the oldest entry still held, size()-1 is the most
    // recent.
    const Entry& at(std::size_t logicalIndex) const {
        const std::size_t total = totalRecorded();
        const std::size_t oldestSeq = (total <= Capacity) ? 0 : (total - Capacity);
        return entries_[(oldestSeq + logicalIndex) % Capacity];
    }

private:
    std::array<Entry, Capacity> entries_{};
    std::atomic<std::size_t> writeCount_{0};
};

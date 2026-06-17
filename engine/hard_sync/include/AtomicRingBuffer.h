#pragma once

#include <array>
#include <atomic>
#include <cstddef>

// Lock-free single-producer/single-consumer ring buffer. push() is called from
// the UI/sequencer thread, pop() from the audio thread; neither blocks or allocates.
template <typename T, std::size_t Capacity>
class AtomicRingBuffer {
public:
    bool push(const T& item) {
        const std::size_t head = head_.load(std::memory_order_relaxed);
        const std::size_t nextHead = (head + 1) % Capacity;
        if (nextHead == tail_.load(std::memory_order_acquire)) {
            return false; // full
        }
        buffer_[head] = item;
        head_.store(nextHead, std::memory_order_release);
        return true;
    }

    bool pop(T& outItem) {
        const std::size_t tail = tail_.load(std::memory_order_relaxed);
        if (tail == head_.load(std::memory_order_acquire)) {
            return false; // empty
        }
        outItem = buffer_[tail];
        tail_.store((tail + 1) % Capacity, std::memory_order_release);
        return true;
    }

private:
    std::array<T, Capacity> buffer_{};
    std::atomic<std::size_t> head_{0};
    std::atomic<std::size_t> tail_{0};
};

/** Typed, synchronous event queue. Flush drains atomically per tick. */
export class EventBus<A> {
  private queue: A[] = [];

  dispatch(action: A): void {
    this.queue.push(action);
  }

  /** Drain and return all queued actions, leaving the queue empty. */
  flush(): A[] {
    const actions = this.queue;
    this.queue    = [];
    return actions;
  }

  get size(): number {
    return this.queue.length;
  }
}

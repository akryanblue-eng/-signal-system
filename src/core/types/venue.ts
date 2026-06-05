/** A named artist or performer tracked on the manifold. */
export interface Artist {
  id: string;
  displayName: string;
}

/** A live venue session with artist context. */
export interface VenueSession {
  sessionId: string;
  artistId: string;
  startTime: number;
  endTime?: number;
}

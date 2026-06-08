/// Append-only SQLite event ledger.
///
/// SQLite is a byte ledger here — not a semantic layer. It stores
/// already-validated canonical bytes in strict sequence order and returns
/// them in that same order. It does not interpret, project, or derive state.
use rusqlite::{Connection, params};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum LedgerError {
    #[error("sqlite: {0}")]
    Sqlite(#[from] rusqlite::Error),
}

pub struct Ledger {
    conn: Connection,
}

impl Ledger {
    pub fn open(path: &str) -> Result<Self, LedgerError> {
        let conn = Connection::open(path)?;
        // STRICT enforces column types; WAL mode gives safe concurrent readers.
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             CREATE TABLE IF NOT EXISTS events (
                 seq   INTEGER PRIMARY KEY AUTOINCREMENT,
                 bytes BLOB NOT NULL
             ) STRICT;",
        )?;
        Ok(Self { conn })
    }

    pub fn open_in_memory() -> Result<Self, LedgerError> {
        let conn = Connection::open_in_memory()?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS events (
                 seq   INTEGER PRIMARY KEY AUTOINCREMENT,
                 bytes BLOB NOT NULL
             ) STRICT;",
        )?;
        Ok(Self { conn })
    }

    /// Append canonical bytes. Returns the assigned sequence number.
    /// Caller is responsible for ensuring bytes are already canonically encoded.
    pub fn append(&self, bytes: &[u8]) -> Result<u64, LedgerError> {
        self.conn
            .execute("INSERT INTO events (bytes) VALUES (?1)", params![bytes])?;
        Ok(self.conn.last_insert_rowid() as u64)
    }

    /// Read all events in strict ascending sequence order.
    pub fn read_ordered(&self) -> Result<Vec<Vec<u8>>, LedgerError> {
        let mut stmt = self
            .conn
            .prepare("SELECT bytes FROM events ORDER BY seq ASC")?;
        let rows = stmt.query_map([], |row| row.get::<_, Vec<u8>>(0))?;
        rows.collect::<Result<Vec<_>, _>>().map_err(Into::into)
    }

    /// Read a single event by sequence number. Returns None if seq not found.
    pub fn read_at(&self, seq: u64) -> Result<Option<Vec<u8>>, LedgerError> {
        let mut stmt = self
            .conn
            .prepare("SELECT bytes FROM events WHERE seq = ?1")?;
        let mut rows = stmt.query(params![seq as i64])?;
        match rows.next()? {
            Some(row) => Ok(Some(row.get(0)?)),
            None => Ok(None),
        }
    }

    pub fn len(&self) -> Result<u64, LedgerError> {
        let count: i64 =
            self.conn
                .query_row("SELECT COUNT(*) FROM events", [], |row| row.get(0))?;
        Ok(count as u64)
    }
}

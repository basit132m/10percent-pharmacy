import { useNotificationLog } from '../hooks/useFirestore';
import { formatTimestamp } from '../lib/offers';

export function NotificationLogPage() {
  const { data: entries, loading, error } = useNotificationLog();

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Notification Log</h1>
          <p className="muted">Every push sent to the stores, newest first.</p>
        </div>
      </header>

      {error && <p className="alert alert--error">{error}</p>}
      {loading && <p className="muted">Loading…</p>}
      {!loading && entries.length === 0 && (
        <p className="empty">Nothing sent yet.</p>
      )}

      {entries.length > 0 && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Sent</th>
                <th>Message</th>
                <th>Devices</th>
                <th>Delivered</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="muted small">{formatTimestamp(entry.sentAt)}</td>
                  <td>
                    <strong>{entry.title}</strong>
                    <div className="muted small">{entry.body}</div>
                  </td>
                  <td>{entry.recipientCount}</td>
                  <td>
                    {entry.successCount}
                    {entry.failureCount > 0 && (
                      <span className="muted small"> ({entry.failureCount} failed)</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

import { useState, type FormEvent } from 'react';
import { httpsCallable } from 'firebase/functions';

import { Modal } from '../components/Modal';
import { ActiveBadge } from '../components/StatusBadge';
import { useStoreOwners } from '../hooks/useFirestore';
import { functions } from '../lib/firebase';
import { formatTimestamp, type StoreOwner } from '../lib/offers';

const createStoreOwner = httpsCallable(functions, 'createStoreOwner');
const updateStoreOwner = httpsCallable(functions, 'updateStoreOwner');
const setStoreOwnerActive = httpsCallable(functions, 'setStoreOwnerActive');

interface FormState {
  storeName: string;
  ownerName: string;
  phone: string;
  address: string;
  username: string;
  password: string;
}

const EMPTY_FORM: FormState = {
  storeName: '',
  ownerName: '',
  phone: '',
  address: '',
  username: '',
  password: '',
};

export function StoreOwnersPage() {
  const { data: stores, loading, error } = useStoreOwners();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editing, setEditing] = useState<StoreOwner | null>(null);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  function openCreate() {
    setForm(EMPTY_FORM);
    setFormError(null);
    setEditing(null);
    setCreating(true);
  }

  function openEdit(store: StoreOwner) {
    setForm({
      storeName: store.storeName ?? '',
      ownerName: store.ownerName ?? '',
      phone: store.phone ?? '',
      address: store.address ?? '',
      username: store.username,
      password: '',
    });
    setFormError(null);
    setCreating(false);
    setEditing(store);
  }

  function closeForm() {
    setCreating(false);
    setEditing(null);
    setFormError(null);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      if (editing) {
        await updateStoreOwner({
          uid: editing.id,
          storeName: form.storeName.trim(),
          ownerName: form.ownerName.trim(),
          phone: form.phone.trim(),
          address: form.address.trim(),
          // Empty means "leave the current password alone".
          password: form.password,
        });
      } else {
        await createStoreOwner({
          storeName: form.storeName.trim(),
          ownerName: form.ownerName.trim(),
          phone: form.phone.trim(),
          address: form.address.trim(),
          username: form.username.trim().toLowerCase(),
          password: form.password,
        });
      }
      closeForm();
    } catch (caught) {
      setFormError(callableMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(store: StoreOwner) {
    const nextState = !store.isActive;
    const confirmed = window.confirm(
      nextState
        ? `Reactivate "${store.storeName}"? They will be able to log in again.`
        : `Deactivate "${store.storeName}"? They will be logged out and stop receiving offers.`,
    );
    if (!confirmed) return;

    setPageError(null);
    try {
      await setStoreOwnerActive({ uid: store.id, isActive: nextState });
    } catch (caught) {
      setPageError(callableMessage(caught));
    }
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Store Owners</h1>
          <p className="muted">
            Accounts are created here — stores cannot sign themselves up.
          </p>
        </div>
        <button type="button" className="button button--primary" onClick={openCreate}>
          + Add store
        </button>
      </header>

      {(error || pageError) && <p className="alert alert--error">{error ?? pageError}</p>}
      {loading && <p className="muted">Loading stores…</p>}
      {!loading && stores.length === 0 && (
        <p className="empty">No store accounts yet. Add the first one.</p>
      )}

      {stores.length > 0 && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Store</th>
                <th>Username</th>
                <th>Contact</th>
                <th>Added</th>
                <th>Status</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {stores.map((store) => (
                <tr key={store.id} className={store.isActive ? '' : 'row--muted'}>
                  <td>
                    <strong>{store.storeName}</strong>
                    {store.address && <div className="muted small">{store.address}</div>}
                  </td>
                  <td>
                    <code>{store.username}</code>
                  </td>
                  <td>
                    {store.ownerName || '—'}
                    {store.phone && <div className="muted small">{store.phone}</div>}
                  </td>
                  <td className="muted small">{formatTimestamp(store.createdAt)}</td>
                  <td>
                    <ActiveBadge isActive={store.isActive} />
                  </td>
                  <td className="actions">
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => openEdit(store)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className={store.isActive ? 'button button--danger' : 'button button--ghost'}
                      onClick={() => void toggleActive(store)}
                    >
                      {store.isActive ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(creating || editing) && (
        <Modal
          title={editing ? `Edit ${editing.storeName}` : 'Add store owner'}
          onClose={closeForm}
        >
          <form onSubmit={onSubmit}>
            {formError && <p className="alert alert--error">{formError}</p>}

            <label className="field">
              <span>Store name</span>
              <input
                value={form.storeName}
                maxLength={120}
                required
                placeholder="e.g. Al-Shifa Medical Store"
                onChange={(event) => setForm({ ...form, storeName: event.target.value })}
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Owner name (optional)</span>
                <input
                  value={form.ownerName}
                  maxLength={120}
                  onChange={(event) => setForm({ ...form, ownerName: event.target.value })}
                />
              </label>
              <label className="field">
                <span>Phone (optional)</span>
                <input
                  value={form.phone}
                  maxLength={20}
                  placeholder="03001234567"
                  onChange={(event) => setForm({ ...form, phone: event.target.value })}
                />
              </label>
            </div>

            <label className="field">
              <span>Address / area (optional)</span>
              <input
                value={form.address}
                maxLength={300}
                onChange={(event) => setForm({ ...form, address: event.target.value })}
              />
            </label>

            <label className="field">
              <span>Username</span>
              <input
                value={form.username}
                required
                disabled={Boolean(editing)}
                minLength={3}
                maxLength={30}
                pattern="[a-z0-9][a-z0-9._\-]{2,29}"
                placeholder="alshifa"
                onChange={(event) =>
                  setForm({ ...form, username: event.target.value.toLowerCase() })
                }
              />
              <small className="muted">
                {editing
                  ? 'Usernames cannot be changed once the account exists.'
                  : 'Lowercase letters, digits, dot, dash or underscore. The store types this in the app.'}
              </small>
            </label>

            <label className="field">
              <span>{editing ? 'New password (leave blank to keep current)' : 'Password'}</span>
              <input
                type="text"
                value={form.password}
                required={!editing}
                minLength={editing ? undefined : 6}
                maxLength={128}
                autoComplete="off"
                onChange={(event) => setForm({ ...form, password: event.target.value })}
              />
              <small className="muted">
                Shown in plain text so you can write it down for the store owner.
              </small>
            </label>

            <div className="modal__actions">
              <button type="button" className="button button--ghost" onClick={closeForm}>
                Cancel
              </button>
              <button type="submit" className="button button--primary" disabled={busy}>
                {busy ? 'Saving…' : editing ? 'Save changes' : 'Create account'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

function callableMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    return String((error as { message: unknown }).message);
  }
  return 'Something went wrong. Try again.';
}

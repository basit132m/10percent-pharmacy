import { useMemo, useState, type FormEvent } from 'react';
import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  serverTimestamp,
  updateDoc,
} from 'firebase/firestore';

import { Modal } from '../components/Modal';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth } from '../auth/AuthContext';
import { useOffers } from '../hooks/useFirestore';
import { db, OFFERS } from '../lib/firebase';
import {
  computeOfferStatus,
  expiryHint,
  formatDate,
  offerHeadline,
  pharmacyToday,
  STATUS_LABELS,
  type Offer,
  type OfferStatus,
} from '../lib/offers';

type Filter = 'all' | OfferStatus;

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'expiring_soon', label: 'Expiring Soon' },
  { key: 'expired', label: 'Expired' },
];

interface FormState {
  productName: string;
  buyQty: string;
  freeQty: string;
  startDate: string;
  expiryDate: string;
}

function emptyForm(): FormState {
  return {
    productName: '',
    buyQty: '5',
    freeQty: '1',
    startDate: pharmacyToday(),
    expiryDate: '',
  };
}

export function OffersPage() {
  const { user } = useAuth();
  const { data: offers, loading, error } = useOffers();
  const [filter, setFilter] = useState<Filter>('all');
  const [editing, setEditing] = useState<Offer | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const visible = useMemo(
    () => (filter === 'all' ? offers : offers.filter((offer) => offer.status === filter)),
    [offers, filter],
  );

  function openCreate() {
    setForm(emptyForm());
    setFormError(null);
    setEditing(null);
    setCreating(true);
  }

  function openEdit(offer: Offer) {
    setForm({
      productName: offer.productName,
      buyQty: String(offer.buyQty),
      freeQty: String(offer.freeQty),
      startDate: offer.startDate,
      expiryDate: offer.expiryDate,
    });
    setFormError(null);
    setCreating(false);
    setEditing(offer);
  }

  function closeForm() {
    setCreating(false);
    setEditing(null);
    setFormError(null);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!user) return;

    const productName = form.productName.trim();
    const buyQty = Number(form.buyQty);
    const freeQty = Number(form.freeQty);

    if (!productName) return setFormError('Enter the product name.');
    if (!Number.isInteger(buyQty) || buyQty < 1) return setFormError('Buy quantity must be a whole number of at least 1.');
    if (!Number.isInteger(freeQty) || freeQty < 1) return setFormError('Free quantity must be a whole number of at least 1.');
    if (!form.startDate) return setFormError('Pick a start date.');
    if (!form.expiryDate) return setFormError('Pick an expiry date.');
    if (form.expiryDate < form.startDate) return setFormError('Expiry date cannot be before the start date.');

    setBusy(true);
    setFormError(null);
    try {
      const payload = {
        productName,
        buyQty,
        freeQty,
        startDate: form.startDate,
        expiryDate: form.expiryDate,
        // Provisional: the Cloud Functions re-stamp this server-side.
        status: computeOfferStatus(form.expiryDate),
        updatedAt: serverTimestamp(),
      };

      if (editing) {
        await updateDoc(doc(db, OFFERS, editing.id), payload);
      } else {
        // Creating the document is what triggers the push notification.
        await addDoc(collection(db, OFFERS), {
          ...payload,
          createdBy: user.uid,
          notifiedAt: null,
          createdAt: serverTimestamp(),
        });
      }
      closeForm();
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : 'Could not save the offer.');
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(offer: Offer) {
    const confirmed = window.confirm(
      `Delete the offer for "${offer.productName}"? Store owners will stop seeing it.`,
    );
    if (!confirmed) return;
    await deleteDoc(doc(db, OFFERS, offer.id));
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Bonus Offers</h1>
          <p className="muted">
            Publishing an offer sends a push notification to every active store.
          </p>
        </div>
        <button type="button" className="button button--primary" onClick={openCreate}>
          + New offer
        </button>
      </header>

      <div className="tabs">
        {FILTERS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={filter === item.key ? 'tab tab--active' : 'tab'}
            onClick={() => setFilter(item.key)}
          >
            {item.label}
            <span className="tab__count">
              {item.key === 'all'
                ? offers.length
                : offers.filter((offer) => offer.status === item.key).length}
            </span>
          </button>
        ))}
      </div>

      {error && <p className="alert alert--error">{error}</p>}
      {loading && <p className="muted">Loading offers…</p>}
      {!loading && visible.length === 0 && (
        <p className="empty">No offers here yet.</p>
      )}

      {visible.length > 0 && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Offer</th>
                <th>Runs</th>
                <th>Status</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {visible.map((offer) => (
                <tr key={offer.id} className={offer.status === 'expired' ? 'row--muted' : ''}>
                  <td>
                    <strong>{offer.productName}</strong>
                    <div className="muted small">{expiryHint(offer)}</div>
                  </td>
                  <td>{offerHeadline(offer)}</td>
                  <td>
                    {formatDate(offer.startDate)} → {formatDate(offer.expiryDate)}
                  </td>
                  <td>
                    <StatusBadge status={offer.status} />
                  </td>
                  <td className="actions">
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => openEdit(offer)}
                      disabled={offer.status === 'expired'}
                      title={
                        offer.status === 'expired'
                          ? 'Expired offers are kept as a record and cannot be edited'
                          : 'Edit offer'
                      }
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="button button--danger"
                      onClick={() => void onDelete(offer)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(creating || editing) && (
        <Modal title={editing ? 'Edit offer' : 'New bonus offer'} onClose={closeForm}>
          <form onSubmit={onSubmit}>
            {formError && <p className="alert alert--error">{formError}</p>}

            <label className="field">
              <span>Product name</span>
              <input
                value={form.productName}
                maxLength={120}
                required
                placeholder="e.g. Panadol 500mg"
                onChange={(event) => setForm({ ...form, productName: event.target.value })}
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Buy quantity</span>
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={form.buyQty}
                  required
                  onChange={(event) => setForm({ ...form, buyQty: event.target.value })}
                />
              </label>
              <label className="field">
                <span>Free quantity</span>
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={form.freeQty}
                  required
                  onChange={(event) => setForm({ ...form, freeQty: event.target.value })}
                />
              </label>
            </div>

            <div className="field-row">
              <label className="field">
                <span>Start date</span>
                <input
                  type="date"
                  value={form.startDate}
                  required
                  onChange={(event) => setForm({ ...form, startDate: event.target.value })}
                />
              </label>
              <label className="field">
                <span>Expiry date</span>
                <input
                  type="date"
                  value={form.expiryDate}
                  min={form.startDate}
                  required
                  onChange={(event) => setForm({ ...form, expiryDate: event.target.value })}
                />
              </label>
            </div>

            {form.expiryDate && (
              <p className="muted small">
                Will be published as{' '}
                <strong>{STATUS_LABELS[computeOfferStatus(form.expiryDate)]}</strong>.
                {!editing && ' All active stores get a notification straight away.'}
              </p>
            )}

            <div className="modal__actions">
              <button type="button" className="button button--ghost" onClick={closeForm}>
                Cancel
              </button>
              <button type="submit" className="button button--primary" disabled={busy}>
                {busy ? 'Saving…' : editing ? 'Save changes' : 'Publish offer'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

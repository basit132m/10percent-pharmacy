import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { StatusBadge } from '../components/StatusBadge';
import { useOffers, useStoreOwners } from '../hooks/useFirestore';
import { refreshOfferStatuses } from '../lib/api';
import { expiryHint, formatDate, offerHeadline } from '../lib/offers';

export function DashboardPage() {
  const { data: offers, loading: offersLoading } = useOffers();
  const { data: stores, loading: storesLoading } = useStoreOwners();
  const [refreshing, setRefreshing] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const stats = useMemo(() => {
    const active = offers.filter((offer) => offer.status === 'active');
    const expiringSoon = offers.filter((offer) => offer.status === 'expiring_soon');
    return {
      activeOffers: active.length,
      expiringSoon: expiringSoon.length,
      activeStores: stores.filter((store) => store.isActive).length,
      totalStores: stores.length,
      expiringList: expiringSoon,
      recent: offers.slice(0, 5),
    };
  }, [offers, stores]);

  async function onRefresh() {
    setRefreshing(true);
    setNote(null);
    try {
      const { updated } = await refreshOfferStatuses();
      setNote(
        updated === 0
          ? 'All offer statuses were already up to date.'
          : `${updated} offer status(es) updated.`,
      );
    } catch (error) {
      setNote(error instanceof Error ? error.message : 'Could not refresh statuses.');
    } finally {
      setRefreshing(false);
    }
  }

  const loading = offersLoading || storesLoading;

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="muted">
            Statuses update automatically every night — this button is only if you
            want to re-check right now.
          </p>
        </div>
        <button
          type="button"
          className="button button--ghost"
          onClick={() => void onRefresh()}
          disabled={refreshing}
        >
          {refreshing ? 'Checking…' : 'Re-check statuses'}
        </button>
      </header>

      {note && <p className="alert alert--info">{note}</p>}
      {loading && <p className="muted">Loading…</p>}

      <div className="stat-grid">
        <Link to="/offers" className="stat">
          <span className="stat__value">{stats.activeOffers}</span>
          <span className="stat__label">Active offers</span>
        </Link>
        <Link to="/offers" className="stat stat--warn">
          <span className="stat__value">{stats.expiringSoon}</span>
          <span className="stat__label">Expiring in next 3 days</span>
        </Link>
        <Link to="/stores" className="stat">
          <span className="stat__value">{stats.activeStores}</span>
          <span className="stat__label">
            Active stores{' '}
            {stats.totalStores > stats.activeStores && (
              <em className="muted">of {stats.totalStores}</em>
            )}
          </span>
        </Link>
      </div>

      <section className="panel">
        <h2>Expiring soon</h2>
        {stats.expiringList.length === 0 ? (
          <p className="empty">Nothing expires in the next 3 days.</p>
        ) : (
          <ul className="list">
            {stats.expiringList.map((offer) => (
              <li key={offer.id} className="list__item">
                <div>
                  <strong>{offer.productName}</strong>
                  <div className="muted small">
                    {offerHeadline(offer)} · ends {formatDate(offer.expiryDate)}
                  </div>
                </div>
                <span className="muted small">{expiryHint(offer)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h2>Latest offers</h2>
        {stats.recent.length === 0 ? (
          <p className="empty">
            No offers yet. <Link to="/offers">Publish the first one.</Link>
          </p>
        ) : (
          <ul className="list">
            {stats.recent.map((offer) => (
              <li key={offer.id} className="list__item">
                <div>
                  <strong>{offer.productName}</strong>
                  <div className="muted small">{offerHeadline(offer)}</div>
                </div>
                <StatusBadge status={offer.status} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

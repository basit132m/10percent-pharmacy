import { STATUS_LABELS, type OfferStatus } from '../lib/offers';

export function StatusBadge({ status }: { status: OfferStatus }) {
  return <span className={`badge badge--${status}`}>{STATUS_LABELS[status]}</span>;
}

export function ActiveBadge({ isActive }: { isActive: boolean }) {
  return (
    <span className={`badge badge--${isActive ? 'active' : 'expired'}`}>
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

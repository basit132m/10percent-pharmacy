import { useEffect, useState } from 'react';
import {
  collection,
  limit,
  onSnapshot,
  orderBy,
  query,
  where,
  type Query,
} from 'firebase/firestore';

import { db, NOTIFICATIONS_LOG, OFFERS, USERS } from '../lib/firebase';
import type { NotificationLogEntry, Offer, StoreOwner } from '../lib/offers';

interface Live<T> {
  data: T[];
  loading: boolean;
  error: string | null;
}

/** Live list from a Firestore query — the dashboard updates itself. */
function useLiveQuery<T>(buildQuery: () => Query, mapper: (id: string, data: never) => T, deps: unknown[]): Live<T> {
  const [state, setState] = useState<Live<T>>({ data: [], loading: true, error: null });

  useEffect(() => {
    setState((previous) => ({ ...previous, loading: true }));
    const unsubscribe = onSnapshot(
      buildQuery(),
      (snapshot) => {
        setState({
          data: snapshot.docs.map((doc) => mapper(doc.id, doc.data() as never)),
          loading: false,
          error: null,
        });
      },
      (error) => {
        setState({ data: [], loading: false, error: error.message });
      },
    );
    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

export function useOffers(): Live<Offer> {
  return useLiveQuery<Offer>(
    () => query(collection(db, OFFERS), orderBy('createdAt', 'desc')),
    (id, data) => ({ id, ...(data as object) }) as Offer,
    [],
  );
}

export function useStoreOwners(): Live<StoreOwner> {
  return useLiveQuery<StoreOwner>(
    () =>
      query(
        collection(db, USERS),
        where('role', '==', 'store_owner'),
        orderBy('createdAt', 'desc'),
      ),
    (id, data) => ({ id, ...(data as object) }) as StoreOwner,
    [],
  );
}

export function useNotificationLog(max = 50): Live<NotificationLogEntry> {
  return useLiveQuery<NotificationLogEntry>(
    () => query(collection(db, NOTIFICATIONS_LOG), orderBy('sentAt', 'desc'), limit(max)),
    (id, data) => ({ id, ...(data as object) }) as NotificationLogEntry,
    [max],
  );
}

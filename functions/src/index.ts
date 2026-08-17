/**
 * 10% Discount Pharmacy — bonus offer backend.
 *
 * Deployed region is asia-south1 (Mumbai), the closest to Kahror Pakka. The web
 * dashboard must call functions in the same region — see web/src/lib/firebase.ts.
 */
import { setGlobalOptions } from 'firebase-functions/v2';

setGlobalOptions({ region: 'asia-south1', maxInstances: 10 });

export {
  createStoreOwner,
  updateStoreOwner,
  setStoreOwnerActive,
} from './stores';

export {
  dailyOfferStatusCheck,
  refreshOfferStatusesNow,
  syncOfferStatusOnEdit,
} from './offers';

export { onOfferPublished } from './notifications';

package pk.tenpercent.pharmacy.data

import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseUser
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.Query
import com.google.firebase.firestore.Source
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await

/**
 * Store owners sign in with a username. Firebase Auth needs an email, so each
 * username maps to a synthetic address on a domain that receives no mail —
 * the same mapping the backend uses when creating the account.
 */
private const val STORE_LOGIN_DOMAIN = "stores.10percentpharmacy.local"

private const val USERS = "users"
private const val OFFERS = "bonusOffers"

class AccountDisabledException : Exception("This account has been deactivated. Contact the pharmacy.")

/** Single access point to Firebase for the whole app. */
class PharmacyRepository(
    private val auth: FirebaseAuth = FirebaseAuth.getInstance(),
    private val firestore: FirebaseFirestore = FirebaseFirestore.getInstance(),
    private val messaging: FirebaseMessaging = FirebaseMessaging.getInstance(),
) {

    val currentUser: FirebaseUser? get() = auth.currentUser

    /** Emits the signed-in user, or null when signed out. */
    fun authStateFlow(): Flow<FirebaseUser?> = callbackFlow {
        val listener = FirebaseAuth.AuthStateListener { trySend(it.currentUser) }
        auth.addAuthStateListener(listener)
        awaitClose { auth.removeAuthStateListener(listener) }
    }

    suspend fun signIn(username: String, password: String) {
        val email = "${username.trim().lowercase()}@$STORE_LOGIN_DOMAIN"
        val result = auth.signInWithEmailAndPassword(email, password).await()
        val uid = result.user?.uid ?: error("Sign in returned no user")

        // Deactivating a store disables its Auth user, so a disabled account
        // normally fails above. This is the belt-and-braces check for a store
        // that was flagged inactive in Firestore only.
        val profile = firestore.collection(USERS).document(uid).get().await()
        if (profile.getBoolean("isActive") == false) {
            auth.signOut()
            throw AccountDisabledException()
        }

        registerPushToken(uid)
    }

    /** Drops this device's push token first, so a logged-out phone goes quiet. */
    suspend fun signOut() {
        val uid = auth.currentUser?.uid
        if (uid != null) {
            runCatching {
                val token = messaging.token.await()
                firestore.collection(USERS).document(uid)
                    .update("fcmTokens", FieldValue.arrayRemove(token))
                    .await()
            }
        }
        auth.signOut()
    }

    /**
     * Store the device's FCM token on the user document. Called at login and
     * whenever FCM rotates the token.
     */
    suspend fun registerPushToken(uid: String, token: String? = null) {
        val value = token ?: messaging.token.await()
        firestore.collection(USERS).document(uid)
            .update("fcmTokens", FieldValue.arrayUnion(value))
            .await()
    }

    fun profileFlow(uid: String): Flow<StoreProfile?> = callbackFlow {
        val registration = firestore.collection(USERS).document(uid)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.takeIf { it.exists() }?.toStoreProfile())
            }
        awaitClose { registration.remove() }
    }

    /**
     * All offers, newest first, with expired ones pushed to the bottom — they
     * stay visible as a record rather than being hidden.
     */
    fun offersFlow(): Flow<List<Offer>> = callbackFlow {
        val registration = firestore.collection(OFFERS)
            .orderBy("createdAt", Query.Direction.DESCENDING)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                val offers = snapshot?.documents.orEmpty().mapNotNull { it.toOffer() }
                trySend(offers.sortedBy { it.isExpired })
            }
        awaitClose { registration.remove() }
    }

    /** Pull-to-refresh: force a server read; the snapshot listener re-emits. */
    suspend fun refreshOffers() {
        firestore.collection(OFFERS)
            .orderBy("createdAt", Query.Direction.DESCENDING)
            .get(Source.SERVER)
            .await()
    }

    /** Used when a notification is tapped before the feed has loaded. */
    suspend fun offer(offerId: String): Offer? =
        firestore.collection(OFFERS).document(offerId).get().await().toOffer()
}

private fun DocumentSnapshot.toOffer(): Offer? {
    val productName = getString("productName") ?: return null
    return Offer(
        id = id,
        productName = productName,
        buyQty = getLong("buyQty") ?: 0L,
        freeQty = getLong("freeQty") ?: 0L,
        startDate = getString("startDate").orEmpty(),
        expiryDate = getString("expiryDate").orEmpty(),
        status = OfferStatus.from(getString("status")),
        createdAt = getTimestamp("createdAt"),
    )
}

private fun DocumentSnapshot.toStoreProfile(): StoreProfile = StoreProfile(
    uid = id,
    username = getString("username").orEmpty(),
    storeName = getString("storeName").orEmpty(),
    ownerName = getString("ownerName"),
    phone = getString("phone"),
    address = getString("address"),
    isActive = getBoolean("isActive") ?: true,
)

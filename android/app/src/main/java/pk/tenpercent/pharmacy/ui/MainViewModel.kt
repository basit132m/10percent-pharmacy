package pk.tenpercent.pharmacy.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.auth.FirebaseAuthInvalidCredentialsException
import com.google.firebase.auth.FirebaseAuthInvalidUserException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import pk.tenpercent.pharmacy.data.AccountDisabledException
import pk.tenpercent.pharmacy.data.Offer
import pk.tenpercent.pharmacy.data.PharmacyRepository
import pk.tenpercent.pharmacy.data.StoreProfile

sealed interface SessionState {
    data object Loading : SessionState
    data object SignedOut : SessionState
    data class SignedIn(val uid: String) : SessionState
}

data class FeedState(
    val offers: List<Offer> = emptyList(),
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val error: String? = null,
)

class MainViewModel(
    private val repository: PharmacyRepository = PharmacyRepository(),
) : ViewModel() {

    private val _session = MutableStateFlow<SessionState>(SessionState.Loading)
    val session: StateFlow<SessionState> = _session.asStateFlow()

    private val _feed = MutableStateFlow(FeedState())
    val feed: StateFlow<FeedState> = _feed.asStateFlow()

    private val _profile = MutableStateFlow<StoreProfile?>(null)
    val profile: StateFlow<StoreProfile?> = _profile.asStateFlow()

    private val _signingIn = MutableStateFlow(false)
    val signingIn: StateFlow<Boolean> = _signingIn.asStateFlow()

    private val _loginError = MutableStateFlow<String?>(null)
    val loginError: StateFlow<String?> = _loginError.asStateFlow()

    private var dataJob: Job? = null

    init {
        viewModelScope.launch {
            repository.authStateFlow().collectLatest { user ->
                dataJob?.cancel()
                if (user == null) {
                    _session.value = SessionState.SignedOut
                    _feed.value = FeedState()
                    _profile.value = null
                } else {
                    _session.value = SessionState.SignedIn(user.uid)
                    dataJob = observeData(user.uid)
                }
            }
        }
    }

    private fun observeData(uid: String): Job = viewModelScope.launch {
        launch {
            repository.offersFlow()
                .catch { error ->
                    _feed.value = _feed.value.copy(
                        loading = false,
                        refreshing = false,
                        error = error.message ?: "Could not load offers.",
                    )
                }
                .collectLatest { offers ->
                    _feed.value = FeedState(offers = offers, loading = false, refreshing = false)
                }
        }
        launch {
            repository.profileFlow(uid)
                .catch { _profile.value = null }
                .collectLatest { storeProfile ->
                    _profile.value = storeProfile
                    // The admin can deactivate a store while the app is open.
                    if (storeProfile != null && !storeProfile.isActive) {
                        signOut()
                    }
                }
        }
    }

    fun signIn(username: String, password: String) {
        if (_signingIn.value) return
        _signingIn.value = true
        _loginError.value = null
        viewModelScope.launch {
            runCatching { repository.signIn(username, password) }
                .onFailure { _loginError.value = loginMessage(it) }
            _signingIn.value = false
        }
    }

    fun dismissLoginError() {
        _loginError.value = null
    }

    fun refresh() {
        if (_feed.value.refreshing) return
        _feed.value = _feed.value.copy(refreshing = true, error = null)
        viewModelScope.launch {
            runCatching { repository.refreshOffers() }
                .onFailure {
                    _feed.value = _feed.value.copy(
                        error = "Could not refresh. Check your connection.",
                    )
                }
            _feed.value = _feed.value.copy(refreshing = false)
        }
    }

    fun signOut() {
        viewModelScope.launch { repository.signOut() }
    }

    /** Registers a rotated FCM token against the signed-in store. */
    fun onPushTokenRefreshed(token: String) {
        val uid = (_session.value as? SessionState.SignedIn)?.uid ?: return
        viewModelScope.launch { runCatching { repository.registerPushToken(uid, token) } }
    }

    fun offerById(offerId: String): Offer? = _feed.value.offers.firstOrNull { it.id == offerId }

    suspend fun loadOffer(offerId: String): Offer? =
        offerById(offerId) ?: runCatching { repository.offer(offerId) }.getOrNull()

    private fun loginMessage(error: Throwable): String = when (error) {
        is AccountDisabledException -> error.message!!
        is FirebaseAuthInvalidUserException ->
            "This account is not active. Contact the pharmacy."
        is FirebaseAuthInvalidCredentialsException -> "Wrong username or password."
        else -> "Could not sign in. Check your internet connection."
    }
}

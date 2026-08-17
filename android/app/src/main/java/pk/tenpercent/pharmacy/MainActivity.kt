package pk.tenpercent.pharmacy

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.google.firebase.messaging.FirebaseMessaging
import pk.tenpercent.pharmacy.data.Offer
import pk.tenpercent.pharmacy.data.StoreProfile
import pk.tenpercent.pharmacy.messaging.OfferMessagingService.Companion.EXTRA_OFFER_ID
import pk.tenpercent.pharmacy.ui.FeedState
import pk.tenpercent.pharmacy.ui.LoginScreen
import pk.tenpercent.pharmacy.ui.MainViewModel
import pk.tenpercent.pharmacy.ui.OfferDetailScreen
import pk.tenpercent.pharmacy.ui.OfferFeedScreen
import pk.tenpercent.pharmacy.ui.ProfileScreen
import pk.tenpercent.pharmacy.ui.SessionState
import pk.tenpercent.pharmacy.ui.theme.PharmacyTheme

private object Routes {
    const val FEED = "feed"
    const val PROFILE = "profile"
    const val OFFER = "offer/{offerId}"

    fun offer(offerId: String) = "offer/$offerId"
}

class MainActivity : ComponentActivity() {

    /** Offer id carried in from a tapped notification, consumed once. */
    private var pendingOfferId by mutableStateOf<String?>(null)

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) {
                // Make sure the freshly usable token reaches the backend.
                FirebaseMessaging.getInstance().token
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pendingOfferId = intent?.getStringExtra(EXTRA_OFFER_ID)

        setContent {
            PharmacyTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    PharmacyApp(
                        pendingOfferId = pendingOfferId,
                        onPendingOfferHandled = { pendingOfferId = null },
                        onSignedIn = ::askForNotificationPermission,
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        pendingOfferId = intent.getStringExtra(EXTRA_OFFER_ID)
    }

    private fun askForNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}

@Composable
private fun PharmacyApp(
    pendingOfferId: String?,
    onPendingOfferHandled: () -> Unit,
    onSignedIn: () -> Unit,
    viewModel: MainViewModel = viewModel(),
) {
    val session by viewModel.session.collectAsState()
    val feed by viewModel.feed.collectAsState()
    val profile by viewModel.profile.collectAsState()
    val signingIn by viewModel.signingIn.collectAsState()
    val loginError by viewModel.loginError.collectAsState()
    val navController = rememberNavController()

    when (session) {
        SessionState.Loading -> Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            CircularProgressIndicator()
        }

        SessionState.SignedOut -> LoginScreen(
            signingIn = signingIn,
            errorMessage = loginError,
            onSignIn = viewModel::signIn,
            onErrorShown = viewModel::dismissLoginError,
        )

        is SessionState.SignedIn -> {
            LaunchedEffect(session) { onSignedIn() }

            // A tapped notification jumps straight to that offer.
            LaunchedEffect(pendingOfferId) {
                val offerId = pendingOfferId ?: return@LaunchedEffect
                navController.navigate(Routes.offer(offerId))
                onPendingOfferHandled()
            }

            SignedInNavHost(
                navController = navController,
                viewModel = viewModel,
                feed = feed,
                storeName = profile?.storeName,
                profile = profile,
            )
        }
    }
}

@Composable
private fun SignedInNavHost(
    navController: NavHostController,
    viewModel: MainViewModel,
    feed: FeedState,
    storeName: String?,
    profile: StoreProfile?,
) {
    NavHost(navController = navController, startDestination = Routes.FEED) {
        composable(Routes.FEED) {
            OfferFeedScreen(
                state = feed,
                storeName = storeName,
                onRefresh = viewModel::refresh,
                onOfferClick = { navController.navigate(Routes.offer(it.id)) },
                onProfileClick = { navController.navigate(Routes.PROFILE) },
            )
        }

        composable(Routes.OFFER) { backStackEntry ->
            val offerId = backStackEntry.arguments?.getString("offerId").orEmpty()
            // Usually already in the feed; fetched directly when opened from a
            // notification before the feed has loaded.
            val offer by produceState<Offer?>(
                initialValue = viewModel.offerById(offerId),
                key1 = offerId,
                key2 = feed.offers,
            ) {
                value = viewModel.loadOffer(offerId)
            }
            OfferDetailScreen(
                offer = offer,
                loading = feed.loading,
                onBack = { navController.popBackStack() },
            )
        }

        composable(Routes.PROFILE) {
            ProfileScreen(
                profile = profile,
                onBack = { navController.popBackStack() },
                onLogout = viewModel::signOut,
            )
        }
    }
}

package pk.tenpercent.pharmacy.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import pk.tenpercent.pharmacy.data.Offer
import pk.tenpercent.pharmacy.data.OfferStatus
import pk.tenpercent.pharmacy.data.formatOfferDate
import pk.tenpercent.pharmacy.ui.theme.Amber50
import pk.tenpercent.pharmacy.ui.theme.Amber600
import pk.tenpercent.pharmacy.ui.theme.Slate100
import pk.tenpercent.pharmacy.ui.theme.Slate500
import pk.tenpercent.pharmacy.ui.theme.Teal50
import pk.tenpercent.pharmacy.ui.theme.Teal700

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OfferFeedScreen(
    state: FeedState,
    storeName: String?,
    onRefresh: () -> Unit,
    onOfferClick: (Offer) -> Unit,
    onProfileClick: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Bonus Offers", fontWeight = FontWeight.SemiBold)
                        if (!storeName.isNullOrBlank()) {
                            Text(
                                text = storeName,
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = onProfileClick) {
                        Icon(Icons.Filled.Person, contentDescription = "Profile")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    actionIconContentColor = MaterialTheme.colorScheme.onPrimary,
                ),
            )
        },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = state.refreshing,
            onRefresh = onRefresh,
            modifier = Modifier
                .padding(padding)
                .fillMaxSize(),
        ) {
            when {
                state.loading && state.offers.isEmpty() -> CenteredMessage("Loading offers…")

                state.offers.isEmpty() -> CenteredMessage(
                    state.error ?: "No bonus offers yet.\nPull down to refresh.",
                )

                else -> LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    if (state.error != null) {
                        item {
                            Text(
                                text = state.error,
                                color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                    items(state.offers, key = { it.id }) { offer ->
                        OfferCard(offer = offer, onClick = { onOfferClick(offer) })
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OfferCard(offer: Offer, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            // Expired offers stay in the list but recede visually.
            .alpha(if (offer.isExpired) 0.55f else 1f),
        colors = CardDefaults.cardColors(
            containerColor = if (offer.isExpired) {
                MaterialTheme.colorScheme.surfaceVariant
            } else {
                MaterialTheme.colorScheme.surface
            },
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = if (offer.isExpired) 0.dp else 2.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Text(
                    text = offer.productName,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f, fill = false),
                )
                StatusChip(offer.status)
            }
            Text(
                text = offer.headline,
                style = MaterialTheme.typography.titleLarge,
                color = if (offer.isExpired) Slate500 else MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(top = 6.dp),
            )
            Text(
                text = if (offer.isExpired) {
                    "Expired on ${formatOfferDate(offer.expiryDate)}"
                } else {
                    "Valid until ${formatOfferDate(offer.expiryDate)}"
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
    }
}

@Composable
fun StatusChip(status: OfferStatus) {
    val (background, foreground) = when (status) {
        OfferStatus.ACTIVE -> Teal50 to Teal700
        OfferStatus.EXPIRING_SOON -> Amber50 to Amber600
        OfferStatus.EXPIRED -> Slate100 to Slate500
    }
    Box(
        modifier = Modifier
            .background(background, RoundedCornerShape(percent = 50))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(
            text = status.label,
            color = foreground,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun CenteredMessage(message: String) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            // Scrollable so the pull-to-refresh gesture works on an empty feed.
            .verticalScroll(rememberScrollState())
            .padding(32.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = message,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

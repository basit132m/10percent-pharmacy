package pk.tenpercent.pharmacy.data

import com.google.firebase.Timestamp
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/**
 * Offer statuses are decided on the server (see functions/src/status.ts) so
 * every store sees the same badge. The app only maps the stored string.
 */
enum class OfferStatus(val stored: String, val label: String) {
    ACTIVE("active", "Active"),
    EXPIRING_SOON("expiring_soon", "Expiring Soon"),
    EXPIRED("expired", "Expired");

    companion object {
        fun from(value: String?): OfferStatus =
            entries.firstOrNull { it.stored == value } ?: ACTIVE
    }
}

data class Offer(
    val id: String,
    val productName: String,
    val buyQty: Long,
    val freeQty: Long,
    val startDate: String,
    val expiryDate: String,
    val status: OfferStatus,
    val createdAt: Timestamp?,
) {
    val headline: String get() = "Buy $buyQty Get $freeQty Free"

    val isExpired: Boolean get() = status == OfferStatus.EXPIRED
}

data class StoreProfile(
    val uid: String,
    val username: String,
    val storeName: String,
    val ownerName: String?,
    val phone: String?,
    val address: String?,
    val isActive: Boolean,
)

const val PHARMACY_TIME_ZONE = "Asia/Karachi"

private val ISO_DATE = SimpleDateFormat("yyyy-MM-dd", Locale.US).apply {
    timeZone = TimeZone.getTimeZone(PHARMACY_TIME_ZONE)
}

private val DISPLAY_DATE = SimpleDateFormat("d MMM yyyy", Locale.US).apply {
    timeZone = TimeZone.getTimeZone(PHARMACY_TIME_ZONE)
}

/** '2026-08-17' -> '17 Aug 2026'; returns the input unchanged if unparseable. */
fun formatOfferDate(isoDate: String): String =
    runCatching { DISPLAY_DATE.format(ISO_DATE.parse(isoDate)!!) }.getOrDefault(isoDate)

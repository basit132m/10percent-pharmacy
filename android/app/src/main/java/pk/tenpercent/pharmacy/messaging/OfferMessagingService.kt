package pk.tenpercent.pharmacy.messaging

import android.app.PendingIntent
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import pk.tenpercent.pharmacy.MainActivity
import pk.tenpercent.pharmacy.R

/**
 * Receives offer pushes. When the app is in the foreground FCM does not post a
 * notification itself, so we build one here; either way the tap carries the
 * offer id through to the detail screen.
 */
class OfferMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        val uid = FirebaseAuth.getInstance().currentUser?.uid ?: return
        // Fire-and-forget: if it fails the app re-registers on the next login.
        FirebaseFirestore.getInstance()
            .collection("users")
            .document(uid)
            .update("fcmTokens", FieldValue.arrayUnion(token))
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val offerId = message.data[EXTRA_OFFER_ID]
        val title = message.notification?.title
            ?: message.data["title"]
            ?: getString(R.string.app_name)
        val body = message.notification?.body
            ?: message.data["body"]
            ?: "A new bonus offer is available."

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra(EXTRA_OFFER_ID, offerId)
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            offerId?.hashCode() ?: 0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = NotificationCompat.Builder(
            this,
            getString(R.string.notification_channel_id),
        )
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()

        val manager = NotificationManagerCompat.from(this)
        if (manager.areNotificationsEnabled()) {
            // Permission is guaranteed here: areNotificationsEnabled() is false
            // until the user grants POST_NOTIFICATIONS on Android 13+.
            @Suppress("MissingPermission")
            manager.notify(offerId?.hashCode() ?: System.currentTimeMillis().toInt(), notification)
        }
    }

    companion object {
        const val EXTRA_OFFER_ID = "offerId"
    }
}

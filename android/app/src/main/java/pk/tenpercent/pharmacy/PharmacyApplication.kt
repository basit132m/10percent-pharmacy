package pk.tenpercent.pharmacy

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class PharmacyApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    /**
     * The channel id must match `default_notification_channel_id` in the
     * manifest and the `channelId` the backend sends with each push.
     */
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            getString(R.string.notification_channel_id),
            getString(R.string.notification_channel_name),
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = getString(R.string.notification_channel_description)
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }
}

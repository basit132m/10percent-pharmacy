package pk.tenpercent.pharmacy.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Teal700 = Color(0xFF0F766E)
val Teal600 = Color(0xFF0D9488)
val Teal50 = Color(0xFFF0FDFA)
val Amber600 = Color(0xFFD97706)
val Amber50 = Color(0xFFFFFBEB)
val Slate700 = Color(0xFF334155)
val Slate500 = Color(0xFF64748B)
val Slate200 = Color(0xFFE2E8F0)
val Slate100 = Color(0xFFF1F5F9)
val Slate50 = Color(0xFFF8FAFC)

private val LightColors = lightColorScheme(
    primary = Teal700,
    onPrimary = Color.White,
    primaryContainer = Teal50,
    onPrimaryContainer = Teal700,
    secondary = Teal600,
    background = Slate50,
    onBackground = Color(0xFF0F172A),
    surface = Color.White,
    onSurface = Color(0xFF0F172A),
    surfaceVariant = Slate100,
    onSurfaceVariant = Slate500,
    outline = Slate200,
)

private val DarkColors = darkColorScheme(
    primary = Teal600,
    onPrimary = Color.White,
    primaryContainer = Color(0xFF134E4A),
    onPrimaryContainer = Teal50,
    secondary = Teal600,
)

@Composable
fun PharmacyTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}

# Firestore maps documents onto these classes reflectively, so keep their
# fields and constructors intact in release builds.
-keepclassmembers class pk.tenpercent.pharmacy.data.** {
    <init>();
    <fields>;
}
-keepnames class pk.tenpercent.pharmacy.data.**

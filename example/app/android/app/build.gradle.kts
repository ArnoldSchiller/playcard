// android/app/build.gradle.kts

// import java.util.Properties // Nicht benötigt für Debug-Build im Git
// import java.io.FileInputStream // Nicht benötigt für Debug-Build im Git

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    // Der eindeutige Namespace deiner App. Wichtig für die App-Identität und Veröffentlichung.
    // 
    namespace = "de.jaquearnoux.playcard_app"

    // Die kompilierte SDK-Version. Stelle sicher, dass du diese SDK-Version in Android Studio installiert hast.
    compileSdk = flutter.compileSdkVersion

    sourceSets {
        main.java.srcDirs += "src/main/kotlin"
    }

    defaultConfig {
        // Die Anwendungs-ID (Package Name). Muss mit dem Namespace übereinstimmen.
        applicationId = "de.jaquearnoux.playcard_app"
        // Die minimale Android-Version, die deine App unterstützt.
        minSdk = flutter.minSdkVersion
        // Die Ziel-Android-Version. Sollte die neueste stabile Version sein.
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode.toInt()
        versionName = flutter.versionName

        // Explizite Festlegung der Android NDK-Version, die von den Plugins benötigt wird.
        // Wichtig für die Kompatibilität.
        ndkVersion = "27.0.12077973"
    }

    // Java-Kompatibilitätseinstellungen.
    // Ich empfehle, bei Java 17 zu bleiben, wenn dein System es unterstützt,
    // da es moderner ist. Wenn Probleme auf Version 11 zurückgehen.
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for release builds.
            // DAS HIER IST AUSKOMMENTIERT / ENTFERNT, DA ES NUR FÜR RELEASE-BUILDS NOTWENDIG IST
            // UND SENSIBLE DATEN BETREFFEN WÜRDE, DIE NICHT INS GIT GEHÖREN.
            // Beispiel einer Signing-Konfiguration (DIESER BLOCK MUSS LOKAL GEÄNDERT/HINZUGEFÜGT WERDEN,
            // WENN MAN EINE RELEASE-VERSION BAUT UND PUBLIZIEREN WILL):
            /*
            signingConfig = signingConfigs.getByName("release")
            */

            // Ob der Code-Shrinker (R8/ProGuard) für Release-Builds aktiviert ist.
            // Für Debug-Builds oft deaktiviert für schnellere Kompilierung.
            isShrinkResources = true
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
}

flutter {
    source="../.."
}

dependencies {
    // Abhängigkeiten, die für deine Android-Plattform benötigt werden (wenn du welche hast)
    // Beispiel:
    // implementation("androidx.core:core-ktx:1.13.1")
}

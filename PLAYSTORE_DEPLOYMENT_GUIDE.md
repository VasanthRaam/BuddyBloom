# Google Play Store Deployment Guide (Local Gradle Build)

This guide details the step-by-step process of merging code changes to the `main` branch, configuring release signing, building a production-ready Android App Bundle (`.aab`) locally using Gradle, and deploying it to the Google Play Store.

---

## Part 1: Merging Changes to Production (`main`)

Since branch protection rules (rulesets) are active on the `main` branch, you cannot push code directly. You must merge changes via a Pull Request (PR).

### Step 1: Push latest local changes to `develop`
Make sure all your latest features are committed and pushed to the `develop` branch on GitHub:
```bash
git checkout develop
git push origin develop
```

### Step 2: Open a Pull Request (PR) on GitHub
1. Go to your repository on **GitHub** (e.g., `https://github.com/VasanthRaam/mobile`).
2. Click the **Pull Requests** tab, then click **New pull request**.
3. Set **base:** `main` and **compare:** `develop`.
4. Add a descriptive title (e.g., `Release v1.0.0: Settings, DOB picker, and bug fixes`).
5. Click **Create pull request**.

### Step 3: Approve and Merge the PR
1. Review the changes as the repository owner.
2. Approve the PR (or temporarily bypass branch rules if self-approval is restricted).
3. Click **Merge pull request**, then click **Confirm merge**.

---

## Part 2: Configuring Release Signing (Keystore)

Google Play requires all uploaded apps to be signed with a secure, private upload key. 

### Step 1: Generate a Keystore File
If you do not have a production keystore yet, generate one using the Java JDK's `keytool` command in your terminal:
```powershell
keytool -genkey -v -keystore my-upload-key.keystore -alias my-key-alias -keyalg RSA -keysize 2048 -validity 10000
```
> [!IMPORTANT]
> Store this keystore file safely and back it up. If you lose this key, you will not be able to send updates to your app on the Google Play Store.

### Step 2: Reference Keystore in `gradle.properties`
1. Place the generated `my-upload-key.keystore` file in the `mobile/android/app/` folder.
2. Open `mobile/android/gradle.properties` and add the following lines at the bottom (replace passwords with your actual keystore passwords):
   ```properties
   MYAPP_UPLOAD_STORE_FILE=my-upload-key.keystore
   MYAPP_UPLOAD_KEY_ALIAS=my-key-alias
   MYAPP_UPLOAD_STORE_PASSWORD=your_store_password
   MYAPP_UPLOAD_KEY_PASSWORD=your_key_password
   ```

### Step 3: Configure Signing in `build.gradle`
Open `mobile/android/app/build.gradle` and configure the release build type to use the new keystore:

```groovy
signingConfigs {
    debug {
        storeFile file('debug.keystore')
        storePassword 'android'
        keyAlias 'androiddebugkey'
        keyPassword 'android'
    }
    release {
        if (project.hasProperty('MYAPP_UPLOAD_STORE_FILE')) {
            storeFile file(MYAPP_UPLOAD_STORE_FILE)
            storePassword MYAPP_UPLOAD_STORE_PASSWORD
            keyAlias MYAPP_UPLOAD_KEY_ALIAS
            keyPassword MYAPP_UPLOAD_KEY_PASSWORD
        }
    }
}
buildTypes {
    release {
        signingConfig signingConfigs.release
        // ... (keep the rest of your release configuration)
    }
}
```

---

## Part 3: Versioning the App
Before compiling, you must bump the versions in `mobile/android/app/build.gradle` (around lines 94–97):
* **`versionCode`**: Must be incremented by at least `1` for every subsequent release uploaded to Google Play (e.g., if the current version is `1`, set it to `2`).
* **`versionName`**: The user-facing version (e.g., `"1.0.1"`).

```groovy
defaultConfig {
    applicationId 'com.buddybloom.app'
    minSdkVersion rootProject.ext.minSdkVersion
    targetSdkVersion rootProject.ext.targetSdkVersion
    versionCode 2 // Bump this number
    versionName "1.0.1" // Bump this string
    ...
}
```

---

## Part 4: Building the Production Bundle (AAB)

Google Play Store accepts only **Android App Bundle (.aab)** files.

1. Open your terminal and navigate to the native `android` folder:
   ```powershell
   cd mobile/android
   ```
2. Clean any previous build caches:
   ```powershell
   .\gradlew clean
   ```
3. Run the compilation command:
   ```powershell
   .\gradlew bundleRelease
   ```
4. Once completed, your production-ready AAB will be outputted to:
   `mobile/android/app/build/outputs/bundle/release/app-release.aab`

---

## Part 5: Deploying to Google Play Console
1. Log into your **Google Play Console** account.
2. Select your app from the dashboard.
3. In the left menu, navigate to **Release > Production** (or **Testing** if you are doing closed/open tracks).
4. Click **Create new release**.
5. Drag and drop the `app-release.aab` file into the upload section.
6. Write your Release Notes and click **Save and publish**.

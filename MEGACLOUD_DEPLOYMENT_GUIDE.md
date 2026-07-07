# Mega Cloud Sharing & Local APK Build Guide

This guide details the step-by-step process of merging code changes to the `main` branch, building a release `.apk` file locally using Gradle, and uploading/sharing it via Mega Cloud.

---

## Part 1: Merging Changes to Production (`main`)

Even when distributing via Mega Cloud, keeping the production branch (`main`) clean and updated is highly recommended.

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
4. Click **Create pull request**.

### Step 3: Approve and Merge the PR
1. Review and approve the PR as the repository owner.
2. Click **Merge pull request**, then click **Confirm merge**.

---

## Part 2: Building the Release APK Locally

Unlike Google Play, which requires an App Bundle (`.aab`), direct distribution to devices requires an Android Package (`.apk`).

### Step 1: Check Signing Configs
Currently, your project is pre-configured to automatically sign release builds using the standard `debug.keystore`. This allows the APK to run on any device instantly without requiring you to manage production keys:
* No changes to `signingConfigs` in `build.gradle` are necessary for basic direct distribution.

### Step 2: Set the App Version (Optional but recommended)
Open `mobile/android/app/build.gradle` and change the version strings (around lines 94–97) so you can keep track of which build is currently live on Mega:
* **`versionCode`**: Increment this integer (e.g., set to `2`).
* **`versionName`**: Bump the version string (e.g., `"1.0.1"`).

### Step 3: Run the Gradle Compilation Command
1. Open your terminal and navigate to the native `android` directory:
   ```powershell
   cd mobile/android
   ```
2. Clean any old compiled caches:
   ```powershell
   .\gradlew clean
   ```
3. Compile the release APK:
   ```powershell
   .\gradlew assembleRelease
   ```
4. Once compilation completes successfully, locate your newly generated APK at:
   `mobile/android/app/build/outputs/apk/release/app-release.apk`

---

## Part 3: Uploading and Sharing on Mega Cloud

1. Log into your **Mega Cloud** account at [mega.nz](https://mega.nz).
2. Create or navigate to a folder where you want to store the builds (e.g., `BuddyBloom Builds`).
3. Drag and drop the `app-release.apk` file into your Mega browser window to start the upload.
4. Once the upload finishes:
   * Right-click on `app-release.apk`.
   * Select **Get link**.
   * Click **Copy** to copy the shareable URL.
5. Send this link to your users. They can download it directly from their mobile browser, open the `.apk` file, and install it on their devices (they may need to allow "Install from unknown sources" on their phone settings).

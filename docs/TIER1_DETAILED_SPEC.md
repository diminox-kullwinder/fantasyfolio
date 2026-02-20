# FantasyFolio Tier 1: Detailed Feature Specification

## Table of Contents
1. [Authentication System](#1-authentication-system)
2. [User Management](#2-user-management)
3. [User Settings & Preferences](#3-user-settings--preferences)
4. [Dashboard Personalization](#4-dashboard-personalization)
5. [Notification System](#5-notification-system)
6. [Basic Collections](#6-basic-collections)

---

# 1. Authentication System

## 1.1 Overview

FantasyFolio will support multiple ways for users to sign in:

| Method | Description | Use Case |
|--------|-------------|----------|
| **Discord SSO** | Sign in with Discord account | Community/gaming focused users |
| **Google SSO** | Sign in with Google account | Broad accessibility |
| **Apple SSO** | Sign in with Apple ID | iOS/Mac users, privacy-focused |
| **Email/Password** | Traditional signup with email | Users without social accounts, fallback option |

## 1.2 Why These Providers?

- **Discord**: Primary choice for gaming communities. Most tabletop RPG players already have Discord for campaign coordination. Enables future Discord bot integration.
- **Google**: Ubiquitous, most users have a Google account. Low friction signup.
- **Apple**: Required for iOS App Store if we build a mobile app. Privacy-focused users prefer it.
- **Email Fallback**: Some users don't want to link social accounts. Enterprise users may have restrictions.

## 1.3 Authentication Flows

### 1.3.1 New User - SSO Signup (Discord Example)

```
USER JOURNEY:
1. User clicks "Sign in with Discord" button
2. Browser redirects to Discord's authorization page
3. User sees: "FantasyFolio wants to access your: Username, Email"
4. User clicks "Authorize"
5. Discord redirects back to FantasyFolio with authorization code
6. FantasyFolio exchanges code for user info (email, username, avatar)
7. System checks: Does this Discord account exist in our system?
   - NO: Create new user account automatically
     - Display name = Discord username
     - Avatar = Discord avatar
     - Email = Discord email
     - Role = "Player" (default)
   - YES: Log them in
8. User lands on Dashboard, fully authenticated
```

**Time to complete**: ~5 seconds (2 clicks)

### 1.3.2 New User - Email Signup

```
USER JOURNEY:
1. User clicks "Sign up with Email"
2. User enters:
   - Email address
   - Password (minimum 8 chars, 1 uppercase, 1 lowercase, 1 number)
   - Display name
3. User clicks "Create Account"
4. System sends verification email with link
5. User clicks link in email
6. Account verified, user redirected to Dashboard
7. User can now log in with email/password
```

**Time to complete**: ~2 minutes (includes email verification)

### 1.3.3 Returning User - Login

```
USER JOURNEY:
1. User visits FantasyFolio
2. If not logged in, sees Login page with options:
   - "Sign in with Discord" button
   - "Sign in with Google" button  
   - "Sign in with Apple" button
   - OR email/password form
3. User clicks preferred method
4. After authentication, lands on Dashboard
```

### 1.3.4 Linking Multiple SSO Providers

A user who signed up with Discord can later link their Google account:

```
USER JOURNEY:
1. User goes to Settings > Connected Accounts
2. Sees: Discord ✓ Connected | Google: "Connect" button | Apple: "Connect" button
3. Clicks "Connect" next to Google
4. Completes Google OAuth flow
5. Now user can sign in with EITHER Discord OR Google
```

**Why allow this?**
- User loses access to Discord → can still sign in with Google
- Different devices may have different accounts signed in
- Flexibility

### 1.3.5 Forgot Password Flow

```
USER JOURNEY:
1. User clicks "Forgot Password?" on login page
2. Enters email address
3. System sends reset link (valid for 1 hour)
4. User clicks link, enters new password
5. Password updated, user redirected to login
```

## 1.4 Security Features

| Feature | Description |
|---------|-------------|
| **Password Hashing** | Argon2id algorithm (industry standard, resistant to GPU attacks) |
| **Session Tokens** | JWT with 15-minute expiry, auto-refreshes in background |
| **Refresh Tokens** | 7-day expiry, stored securely, can be revoked |
| **Rate Limiting** | 5 login attempts per minute per IP (prevents brute force) |
| **Account Lockout** | After 10 failed attempts, account locked for 15 minutes |
| **HTTPS Only** | All auth traffic encrypted |
| **Secure Cookies** | httpOnly (no JavaScript access), secure flag, sameSite=strict |

## 1.5 Session Management

Users can view and manage their active sessions:

```
Settings > Security > Active Sessions

+--------------------------------------------------+
| Active Sessions                                   |
+--------------------------------------------------+
| 🖥️ Windows PC - Chrome                           |
|    IP: 192.168.1.100                             |
|    Last active: 5 minutes ago                    |
|    [Current Session]                             |
+--------------------------------------------------+
| 📱 iPhone - Safari                               |
|    IP: 192.168.1.101                             |
|    Last active: 2 days ago                       |
|    [Revoke]                                      |
+--------------------------------------------------+
| [Sign Out All Other Sessions]                    |
+--------------------------------------------------+
```

---

# 2. User Management

## 2.1 User Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| **Admin** | System administrator | Full access, user management, system settings |
| **GM** | Game Master | Create campaigns, share collections, invite players |
| **Player** | Standard user (default) | View shared content, create personal collections |
| **Guest** | Temporary access via link | View-only access to specific shared content |

## 2.2 User Profile

Every user has a profile containing:

| Field | Description | Editable |
|-------|-------------|----------|
| **Display Name** | Shown throughout the app | ✓ |
| **Email** | For login and notifications | ✓ (requires verification) |
| **Avatar** | Profile picture (from SSO or uploaded) | ✓ |
| **Bio** | Short description | ✓ |
| **Role** | Permission level | Admin only |
| **Member Since** | Account creation date | No |
| **Last Login** | Most recent login time | No |

## 2.3 JIT (Just-In-Time) Provisioning

When a user signs in with SSO for the first time, their account is automatically created:

```
Auto-populated from Discord:
- Display Name: "DragonSlayer42"
- Email: "user@example.com"  
- Avatar: [Discord profile picture]
- Role: "Player"
- Timezone: Detected from browser
- Theme: Dark (default)
```

No manual account creation needed - sign in once and you're set up.

---

# 3. User Settings & Preferences

## 3.1 Settings Categories

### 3.1.1 Account Settings
```
+------------------------------------------+
| Account Settings                          |
+------------------------------------------+
| Display Name: [DragonSlayer42        ]   |
| Email: [user@example.com             ]   |
|        [Change Email] [Verify Email]     |
|                                          |
| Password:                                |
| [Change Password]                        |
|                                          |
| Connected Accounts:                      |
| ✓ Discord (DragonSlayer42#1234)         |
|   [Disconnect]                           |
| ○ Google                                 |
|   [Connect]                              |
| ○ Apple                                  |
|   [Connect]                              |
|                                          |
| [Delete Account]                         |
+------------------------------------------+
```

### 3.1.2 Appearance Settings
```
+------------------------------------------+
| Appearance                               |
+------------------------------------------+
| Theme:                                   |
| ● Dark Mode (default)                    |
|   - Dark backgrounds, light text         |
|   - Easy on eyes, good for long sessions |
|                                          |
| ○ Light Mode                             |
|   - Light backgrounds, dark text         |
|   - Better for bright environments       |
|                                          |
| ○ Parchment Mode                         |
|   - Aged paper aesthetic                 |
|   - Immersive fantasy feel               |
|   - Subtle textures and warm colors      |
|                                          |
| Preview: [Live preview of selected theme]|
+------------------------------------------+
```

### 3.1.3 Regional Settings
```
+------------------------------------------+
| Regional                                 |
+------------------------------------------+
| Timezone: [America/Los_Angeles (PST)  ▼] |
|   - Used for: Notification timing,       |
|     "Last modified" displays,            |
|     Scheduled exports                    |
|                                          |
| Locale: [English (US)                 ▼] |
|   - Date format: MM/DD/YYYY              |
|   - Number format: 1,234.56              |
|                                          |
| First day of week: [Sunday            ▼] |
+------------------------------------------+
```

### 3.1.4 Privacy Settings
```
+------------------------------------------+
| Privacy                                  |
+------------------------------------------+
| Profile Visibility:                      |
| ○ Public - Anyone can see your profile   |
| ● Friends Only - Only campaign members   |
| ○ Private - Only you can see             |
|                                          |
| Show Online Status:                      |
| [✓] Show when I'm online to campaign     |
|     members                              |
|                                          |
| Activity:                                |
| [✓] Show my recently viewed assets to    |
|     campaign members                     |
+------------------------------------------+
```

---

# 4. Dashboard Personalization

## 4.1 Dashboard Overview

The dashboard is the user's home screen - a personalized view showing their most relevant content.

```
+------------------------------------------------------------------+
|  FantasyFolio                    [Search...]         👤 DragonSlayer42 |
+------------------------------------------------------------------+
|                                                                    |
|  Good evening, DragonSlayer42!                     [Customize]     |
|                                                                    |
+---------------------------+--------------------------------------+
|                           |                                      |
|  📌 PINNED TAGS           |  🕐 RECENTLY VIEWED                  |
|  +-------------------+    |  +--------------------------------+  |
|  | dragon      (47)  |    |  | Dragon_Ancient_Red.stl         |  |
|  | dungeon     (123) |    |  | Viewed 5 min ago               |  |
|  | tavern      (31)  |    |  +--------------------------------+  |
|  | npc         (89)  |    |  | Dungeon_Tiles_Set3.zip         |  |
|  +-------------------+    |  | Viewed 2 hours ago             |  |
|  [+ Add Tag]              |  +--------------------------------+  |
|                           |  | Monster_Manual_5e.pdf          |  |
|  📁 FAVORITE FOLDERS      |  | Viewed yesterday               |  |
|  +-------------------+    |  +--------------------------------+  |
|  | Current Campaign  |    |                                      |
|  | Print Queue       |    |  📤 RECENTLY UPLOADED               |
|  | Need to Organize  |    |  +--------------------------------+  |
|  +-------------------+    |  | Goblin_Warband_x10.stl         |  |
|  [+ Add Folder]           |  | Uploaded today 3:42 PM         |  |
|                           |  +--------------------------------+  |
|  📊 QUICK STATS           |  | Tavern_Interior_Map.png        |  |
|  +-------------------+    |  | Uploaded yesterday             |  |
|  | 3D Models: 2,847  |    |  +--------------------------------+  |
|  | PDFs: 1,234       |    |                                      |
|  | Collections: 12   |    |  🔄 RECENTLY MODIFIED               |
|  | Storage: 45.2 GB  |    |  +--------------------------------+  |
|  +-------------------+    |  | "Dragon Encounters" collection  |  |
|                           |  | Added 3 items - 1 hour ago     |  |
+---------------------------+--------------------------------------+
|                                                                    |
|  📂 MY COLLECTIONS (3 shown of 12)                   [View All]    |
|  +------------------+ +------------------+ +------------------+    |
|  | 🐉 Dragons       | | 🏰 Dungeons      | | 👤 NPCs          |    |
|  | 47 items         | | 123 items        | | 89 items         |    |
|  | Updated today    | | Updated 2d ago   | | Updated 1w ago   |    |
|  +------------------+ +------------------+ +------------------+    |
|                                                                    |
+------------------------------------------------------------------+
```

## 4.2 Dashboard Widgets

Users can show/hide and rearrange these widgets:

| Widget | Description | Default |
|--------|-------------|---------|
| **Pinned Tags** | Quick access to frequently used tags | Shown |
| **Favorite Folders** | Bookmarked folder locations | Shown |
| **Quick Stats** | Asset counts and storage usage | Shown |
| **Recently Viewed** | Last 10 assets you looked at | Shown |
| **Recently Uploaded** | Last 10 assets you uploaded | Shown |
| **Recently Modified** | Assets/collections changed recently | Shown |
| **My Collections** | Your collection cards | Shown |
| **Shared With Me** | Collections others shared with you | Shown |
| **Campaign Activity** | Recent activity in your campaigns | Hidden |
| **Print Queue** | Items marked for printing | Hidden |

## 4.3 Customization Options

### 4.3.1 Widget Settings
```
+------------------------------------------+
| Customize Dashboard                       |
+------------------------------------------+
| Drag widgets to reorder, toggle to show/ |
| hide                                      |
|                                          |
| [✓] Pinned Tags         [Drag Handle ≡] |
| [✓] Favorite Folders    [Drag Handle ≡] |
| [✓] Quick Stats         [Drag Handle ≡] |
| [✓] Recently Viewed     [Drag Handle ≡] |
|     - Show last: [10 ▼] items           |
| [✓] Recently Uploaded   [Drag Handle ≡] |
|     - Show last: [10 ▼] items           |
| [✓] Recently Modified   [Drag Handle ≡] |
| [✓] My Collections      [Drag Handle ≡] |
|     - Show: [3 ▼] collections           |
| [✓] Shared With Me      [Drag Handle ≡] |
| [ ] Campaign Activity   [Drag Handle ≡] |
| [ ] Print Queue         [Drag Handle ≡] |
|                                          |
| [Reset to Default]      [Save Changes]   |
+------------------------------------------+
```

### 4.3.2 Pinned Tags Management
```
+------------------------------------------+
| Manage Pinned Tags                        |
+------------------------------------------+
| Click tags to pin/unpin. Pinned tags     |
| appear on your dashboard for quick       |
| filtering.                               |
|                                          |
| YOUR PINNED TAGS:                        |
| [dragon ×] [dungeon ×] [npc ×] [tavern ×]|
|                                          |
| POPULAR TAGS:                            |
| [monster] [terrain] [miniature] [map]    |
| [5e] [pathfinder] [vehicle] [building]   |
|                                          |
| RECENTLY USED:                           |
| [goblin] [undead] [forest] [cave]        |
|                                          |
| Search tags: [____________] 🔍           |
+------------------------------------------+
```

### 4.3.3 Default Sort Preferences
```
+------------------------------------------+
| Default Sort Options                      |
+------------------------------------------+
| When browsing assets, default to:        |
|                                          |
| 3D Models:                               |
| Sort by: [Date Added           ▼]        |
| Order:   [Newest First         ▼]        |
|                                          |
| PDFs/Documents:                          |
| Sort by: [Date Added           ▼]        |
| Order:   [Newest First         ▼]        |
|                                          |
| Collections:                             |
| Sort by: [Last Modified        ▼]        |
| Order:   [Most Recent First    ▼]        |
|                                          |
| Available sort options:                  |
| - Date Added                             |
| - Date Modified                          |
| - Name (A-Z / Z-A)                       |
| - File Size                              |
| - File Type                              |
+------------------------------------------+
```

### 4.3.4 Default View Preferences
```
+------------------------------------------+
| Default View Options                      |
+------------------------------------------+
| 3D Models View:                          |
| ● Grid (thumbnails)                      |
| ○ List (details)                         |
| ○ Compact (small thumbnails)             |
|                                          |
| Thumbnail size: [Medium ▼]               |
| Items per page: [50 ▼]                   |
|                                          |
| PDF View:                                |
| ○ Grid (cover thumbnails)                |
| ● List (with details)                    |
| ○ Compact                                |
|                                          |
| [✓] Show file size in list view          |
| [✓] Show date added in list view         |
| [ ] Show full file path                  |
+------------------------------------------+
```

---

# 5. Notification System

## 5.1 Notification Types

| Type | Trigger | Description |
|------|---------|-------------|
| **Collection Shared** | Someone shares a collection with you | "DragonMaster shared 'Epic Bosses' with you" |
| **Collection Updated** | Items added to a collection you follow | "'Dragon Encounters' has 3 new items" |
| **Campaign Invite** | You're invited to join a campaign | "Join 'Curse of Strahd' campaign?" |
| **Campaign Update** | New content in your campaign | "GM added 2 collections to 'Curse of Strahd'" |
| **Asset Processing** | Upload/indexing complete | "12 new 3D models indexed from 'Dragons.zip'" |
| **System Alert** | Important system messages | "Scheduled maintenance tonight 2-4 AM" |

## 5.2 Notification Delivery Channels

| Channel | Description | Use Case |
|---------|-------------|----------|
| **In-App** | Bell icon with badge, notification drawer | Always on, real-time |
| **Email** | Sent to registered email | Important updates, digests |
| **Discord Webhook** | Posts to a Discord channel | Campaign coordination |

## 5.3 Notification Settings

```
+----------------------------------------------------------+
| Notification Preferences                                   |
+----------------------------------------------------------+
|                                                            |
| DELIVERY CHANNELS                                          |
| +--------------------------------------------------------+ |
| | In-App Notifications                                    | |
| | [✓] Enabled (recommended)                              | |
| +--------------------------------------------------------+ |
| | Email Notifications                                     | |
| | [✓] Enabled                                            | |
| | Email: user@example.com [Change]                       | |
| +--------------------------------------------------------+ |
| | Discord Webhook                                         | |
| | [✓] Enabled                                            | |
| | Webhook URL: https://discord.com/api/webhooks/...      | |
| | [Test Webhook] [Update URL]                            | |
| +--------------------------------------------------------+ |
|                                                            |
| NOTIFICATION RULES                                         |
| +--------------------------------------------------------+ |
| | Rule: Collection Updates                     [Edit] [×] | |
| | Trigger: Any update to collections I follow             | |
| | Frequency: Immediate                                    | |
| | Channels: In-App, Discord                               | |
| +--------------------------------------------------------+ |
| | Rule: Campaign Activity                      [Edit] [×] | |
| | Trigger: Any activity in my campaigns                   | |
| | Frequency: Daily digest                                 | |
| | Channels: Email                                         | |
| +--------------------------------------------------------+ |
| | Rule: New Shared Content                     [Edit] [×] | |
| | Trigger: When content is shared with me                 | |
| | Frequency: Immediate                                    | |
| | Channels: In-App, Email                                 | |
| +--------------------------------------------------------+ |
| [+ Add Notification Rule]                                  |
|                                                            |
| QUIET HOURS                                                |
| [✓] Enable quiet hours (no notifications during this time)|
|     From: [10:00 PM ▼] To: [8:00 AM ▼]                    |
|     Timezone: America/Los_Angeles                         |
|     (Urgent notifications will still come through)        |
|                                                            |
+----------------------------------------------------------+
```

## 5.4 Creating Notification Rules

```
+------------------------------------------+
| Create Notification Rule                  |
+------------------------------------------+
| Rule Name: [Weekly Campaign Digest    ]  |
|                                          |
| TRIGGER                                  |
| When: [Any update               ▼]       |
|                                          |
| To these items:                          |
| [✓] Specific collections:               |
|     [Dragon Encounters ▼] [+ Add]       |
| [✓] Specific campaigns:                 |
|     [Curse of Strahd ▼] [+ Add]         |
| [ ] All collections I follow            |
| [ ] All campaigns I'm in                |
|                                          |
| FREQUENCY                                |
| ○ Immediate - notify right away         |
| ○ Daily digest - once per day at [9 AM] |
| ● Weekly digest - every [Monday] at [9AM]|
|                                          |
| DELIVERY                                 |
| [✓] In-App notification                 |
| [✓] Email                               |
| [ ] Discord Webhook                      |
|                                          |
| [Cancel]                    [Save Rule]  |
+------------------------------------------+
```

---

# 6. Basic Collections

## 6.1 Collection Types

| Type | Visibility | Description |
|------|------------|-------------|
| **Private** | Only you | Personal "lightbox" - saved favorites, to-print queue, etc. |
| **Shared** | Specific users | Share with selected users or campaign members |
| **Public** | Anyone with link | Visible to all logged-in users, searchable |

## 6.2 Creating a Collection

```
+------------------------------------------+
| Create New Collection                     |
+------------------------------------------+
| Name: [Dragon Encounters            ]    |
|                                          |
| Description:                             |
| [All the dragon minis and maps I've     ]|
| [collected for my campaign boss fights  ]|
|                                          |
| Cover Image:                             |
| [📷 Upload Image] or [Use from items]   |
|                                          |
| Visibility:                              |
| ● Private (only you)                     |
| ○ Shared (specific people)               |
| ○ Public (anyone)                        |
|                                          |
| Tags: [dragon] [boss] [encounter] [+]    |
|                                          |
| [Cancel]               [Create Collection]|
+------------------------------------------+
```

## 6.3 Adding Items to Collections

### Method 1: From Asset View
```
Right-click on any asset → "Add to Collection" → Select collection
```

### Method 2: Multi-select
```
1. Click checkbox on multiple assets
2. Click "Add to Collection" in toolbar
3. Select destination collection
```

### Method 3: Drag and Drop
```
Drag asset(s) onto collection in sidebar
```

### Method 4: From Collection View
```
1. Open collection
2. Click "Add Items"
3. Browse/search for items
4. Click items to add
```

## 6.4 Collection View

```
+------------------------------------------------------------------+
| 🐉 Dragon Encounters                                    [⚙️ Edit]  |
+------------------------------------------------------------------+
| Created by DragonSlayer42 | 47 items | Last updated 2 hours ago  |
| Tags: dragon, boss, encounter                                     |
+------------------------------------------------------------------+
| Description:                                                      |
| All the dragon minis and maps I've collected for my campaign     |
| boss fights                                                       |
+------------------------------------------------------------------+
|                                                                   |
| [+ Add Items] [↓ Download All] [📤 Share] [⋮ More]               |
|                                                                   |
| Sort: [Date Added ▼] [Newest First ▼]   View: [Grid] [List]      |
|                                                                   |
| +---------------+ +---------------+ +---------------+             |
| | [Thumbnail]   | | [Thumbnail]   | | [Thumbnail]   |             |
| | Ancient Red   | | Dragon Lair   | | Wyrmling x5   |             |
| | Dragon.stl    | | Map.png       | | Pack.stl      |             |
| | Added 2h ago  | | Added 1d ago  | | Added 3d ago  |             |
| +---------------+ +---------------+ +---------------+             |
|                                                                   |
+------------------------------------------------------------------+
```

## 6.5 Sharing Collections

```
+------------------------------------------+
| Share "Dragon Encounters"                 |
+------------------------------------------+
| Current sharing: Private (only you)      |
|                                          |
| SHARE WITH USERS                         |
| Search users: [____________] 🔍          |
|                                          |
| Shared with:                             |
| +--------------------------------------+ |
| | 👤 PaladinPete                       | |
| |    Permission: [Can View      ▼]     | |
| |    [Remove]                          | |
| +--------------------------------------+ |
| | 👤 WizardWendy                       | |
| |    Permission: [Can Download  ▼]     | |
| |    [Remove]                          | |
| +--------------------------------------+ |
|                                          |
| SHARE WITH CAMPAIGN                      |
| [Share with "Curse of Strahd" campaign]  |
|                                          |
| GUEST LINK                               |
| Generate a link for people without       |
| accounts:                                |
| [Generate Guest Link]                    |
|                                          |
| Active guest links:                      |
| +--------------------------------------+ |
| | Link: ff.app/g/xK9mN2p               | |
| | Created: 2 days ago                  | |
| | Expires: 5 days remaining            | |
| | Views: 12 | Downloads: 3             | |
| | [Copy Link] [QR Code] [Revoke]       | |
| +--------------------------------------+ |
|                                          |
+------------------------------------------+
```

## 6.6 Permission Levels

| Permission | Can View | Can Download | Can Edit | Can Share |
|------------|----------|--------------|----------|-----------|
| **View** | ✓ | - | - | - |
| **Download** | ✓ | ✓ | - | - |
| **Edit** | ✓ | ✓ | ✓ | - |
| **Admin** | ✓ | ✓ | ✓ | ✓ |

## 6.7 Guest Links

Guest links allow sharing with people who don't have accounts:

| Setting | Description |
|---------|-------------|
| **Expiration** | 1 day, 7 days, 30 days, or never |
| **Max Downloads** | Unlimited, or set a limit |
| **Password** | Optional password protection |
| **Allowed Actions** | View only, or View + Download |

---

# Implementation Priority

## Must Have (Week 1-2)
- [ ] Email/password signup and login
- [ ] Discord SSO
- [ ] Basic user profile
- [ ] Dark/Light theme toggle
- [ ] Private collections (create, add items, view)

## Should Have (Week 2-3)
- [ ] Google SSO
- [ ] Apple SSO
- [ ] Dashboard with Recently Viewed/Uploaded
- [ ] Collection sharing with specific users
- [ ] In-app notifications

## Nice to Have (Week 3+)
- [ ] Parchment theme
- [ ] Pinned tags on dashboard
- [ ] Guest links for collections
- [ ] Email notifications
- [ ] Discord webhook notifications
- [ ] Notification rules and digests

---

# Open Questions

1. **Account Deletion**: Should we soft-delete or hard-delete user accounts? (Recommendation: soft-delete with 30-day grace period)

2. **Username Uniqueness**: Should display names be unique, or just use emails as identifiers? (Recommendation: display names don't need to be unique)

3. **Default Role**: Should new users be "Player" or require admin approval? (Recommendation: auto-Player for frictionless onboarding)

4. **Session Duration**: How long before requiring re-login? (Recommendation: 7 days if "Remember Me" checked, otherwise browser session)

5. **Collection Limits**: Should free users have limits on collections/items? (Decision needed for monetization strategy)

---

# 7. Cross-Asset Collections

## 7.1 Overview

Collections can contain **both 3D models AND PDFs/documents**. This reflects real RPG campaign organization where a single adventure needs minis, maps, rules, and handouts together.

## 7.2 Use Cases

| Collection Type | Contents | Example |
|-----------------|----------|---------|
| **Campaign** | Everything for a campaign | Curse of Strahd: adventure PDF + all minis + all maps |
| **Encounter** | Single encounter assets | Dragon Fight: dragon STL + lair map PDF + stat block |
| **Print Session** | Next batch to print | Tonight's Print: 5 minis + reference cards PDF |
| **Theme** | Assets by theme | Undead: zombie STLs + necromancer STLs + undead rules PDF |
| **Source** | From same creator | Loot Studios March: all STLs + painting guide PDF |

## 7.3 Collection View - Mixed Assets

```
+------------------------------------------------------------------+
| 🏰 Curse of Strahd Campaign                           [⚙️ Edit]   |
+------------------------------------------------------------------+
| 47 items (32 models, 15 documents)                                |
+------------------------------------------------------------------+
|                                                                   |
| Filter: [All ▼]  [3D Models]  [PDFs]     Sort: [Type, then Name] |
|                                                                   |
| 📁 DOCUMENTS (15)                                                 |
| +---------------+ +---------------+ +---------------+             |
| | [PDF icon]    | | [PDF icon]    | | [PDF icon]    |             |
| | Curse of      | | Barovia       | | Tarokka       |             |
| | Strahd.pdf    | | Map.pdf       | | Deck.pdf      |             |
| +---------------+ +---------------+ +---------------+             |
|                                                                   |
| 🎲 3D MODELS (32)                                                 |
| +---------------+ +---------------+ +---------------+             |
| | [Thumbnail]   | | [Thumbnail]   | | [Thumbnail]   |             |
| | Strahd.stl    | | Castle        | | Wolves x6.stl |             |
| |               | | Gate.stl      | |               |             |
| +---------------+ +---------------+ +---------------+             |
|                                                                   |
+------------------------------------------------------------------+
```

## 7.4 Adding Items from Either Asset Type

### From 3D Models Browser
```
Right-click any model → Add to Collection → [Select collection]
```

### From PDF/Documents Browser
```
Right-click any PDF → Add to Collection → [Select collection]
```

### From Collection View
```
Click [+ Add Items] → Toggle between:
  [3D Models Tab] | [Documents Tab]
Browse/search and click to add
```

## 7.5 Future: Unified Nav Tree

Eventually, collections could appear as a top-level navigation alongside asset types:

```
+----------------------------------+
| NAVIGATION                       |
+----------------------------------+
| 📁 3D Models                     |
|    └─ By Volume                  |
|    └─ By Folder                  |
|    └─ By Tag                     |
+----------------------------------+
| 📄 Documents                     |
|    └─ By Volume                  |
|    └─ By Folder                  |
|    └─ By Tag                     |
+----------------------------------+
| ⭐ Collections          [+ New]  |
|    └─ 🏰 Curse of Strahd        |
|    └─ 🐉 Dragon Encounters      |
|    └─ 🖨️ Print Queue            |
|    └─ 📥 Shared with Me         |
+----------------------------------+
| 🎮 Campaigns                     |
|    └─ Curse of Strahd (GM)      |
|    └─ Waterdeep (Player)        |
+----------------------------------+
```

## 7.6 Technical: Collection Items Table

```sql
CREATE TABLE collection_items (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    
    -- Asset reference (one of these will be set)
    model_id INTEGER,      -- References models.id (3D assets)
    asset_id INTEGER,      -- References assets.id (PDFs/documents)
    
    -- Metadata
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT,         -- User who added it
    sort_order INTEGER,    -- For manual ordering
    notes TEXT,            -- User notes on this item
    
    -- Constraints
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    CHECK (
        (model_id IS NOT NULL AND asset_id IS NULL) OR
        (model_id IS NULL AND asset_id IS NOT NULL)
    )
);

-- Index for fast lookups
CREATE INDEX idx_collection_items_collection ON collection_items(collection_id);
CREATE INDEX idx_collection_items_model ON collection_items(model_id);
CREATE INDEX idx_collection_items_asset ON collection_items(asset_id);
```

## 7.7 Bulk Operations on Mixed Collections

| Action | Behavior |
|--------|----------|
| **Download All** | Creates ZIP with `/3D/` and `/Documents/` folders |
| **Share** | Recipient sees all items they have permission for |
| **Export List** | CSV/JSON with all items, types indicated |
| **Print Queue** | Only 3D models sent to slicer integration |


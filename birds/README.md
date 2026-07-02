# Birds gallery — Instagram sync

`birds.scott-ouellette.com` shows the top-liked shots from
[@birdsofnorthandover](https://www.instagram.com/birdsofnorthandover/). The
gallery renders from `manifest.json` in this folder (and a cached copy in S3);
`../birds.py` regenerates it from Instagram on a schedule.

## What it can and can't do

- ✅ Rank **your own posts** by like count across your **entire** posting history
  (the API paginates through all of your media), then keep the top `BIRDS_TOP_N`.
- ✅ Re-host each top image to S3, since Instagram's `media_url`s expire.
- ❌ It **cannot** read posts *you* liked on other people's accounts — Instagram
  removed all API access to outbound likes. "Top-shots" therefore means your own
  posts with the most likes.

## One-time setup

1. **Make the account Professional.** In the Instagram app, switch
   `@birdsofnorthandover` to a Business or Creator account (free). `like_count`
   is only returned for Professional accounts' own media.
2. **Create a Meta app** at <https://developers.facebook.com/> and add the
   *Instagram API with Instagram Login* product. Note its **Instagram App ID**
   and **App Secret**, and configure an **OAuth redirect URI** (e.g.
   `https://www.scott-ouellette.com/`). Add yourself as a tester — the app can
   stay in **Development mode** since we only read your own account, so **no Meta
   App Review is needed.**
3. **Mint a long-lived token** with the helper (`../auth.py`):

   ```bash
   export IG_APP_ID=...           # Instagram App ID
   export IG_APP_SECRET=...       # App Secret
   export IG_REDIRECT_URI=https://www.scott-ouellette.com/   # must match the app

   python auth.py url             # open the printed URL, approve, copy the ?code=...
   python auth.py exchange --code PASTE_CODE --save-ssm
   ```

   `--save-ssm` writes the token to SSM Parameter Store (`/birds/instagram_token`,
   SecureString). The daily sync then **auto-refreshes it** (`scheduled_sync`), so
   it never lapses as long as the job runs at least every ~60 days.

## Configuration (environment variables)

| Variable                  | Default                 | Purpose                                        |
|---------------------------|-------------------------|------------------------------------------------|
| `INSTAGRAM_ACCESS_TOKEN`  | —                       | Override token (e.g. local runs); else SSM     |
| `INSTAGRAM_TOKEN_SSM_PARAM` | `/birds/instagram_token` | SSM SecureString holding the long-lived token |
| `INSTAGRAM_USER_ID`       | `me`                    | Usually unnecessary; resolved from token       |
| `BIRDS_S3_BUCKET`         | `zappa-0206au0bc`       | Bucket for re-hosted images + manifest         |
| `BIRDS_S3_PREFIX`         | `birds`                 | Key prefix within the bucket                   |
| `BIRDS_TOP_N`             | `24`                    | How many top shots to keep                     |
| `BIRDS_USE_S3`            | unset                   | Set to read the manifest from S3 at serve time |

## Running the sync

```bash
# Quick local proof with a freshly minted token (no SSM/refresh needed):
INSTAGRAM_ACCESS_TOKEN=xxx python birds.py

# In production it runs daily via the Zappa event in ../zappa_settings.json
# (birds.scheduled_sync) — which refreshes the token, then syncs.
```

A successful run rewrites this `manifest.json` (committed copy = always-works
fallback) and the S3 cache the live site reads first.

## Subdomain

`birds.scott-ouellette.com` is served by the same Lambda via host-based routing
(see `serve_birds_subdomain` in `../index.py`). One-time infra:

```bash
zappa certify production    # provision the ACM cert + API Gateway domain
# then add a Route 53 alias/CNAME: birds.scott-ouellette.com -> the API Gateway domain
```

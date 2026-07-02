#!/usr/bin/env python
"""One-time helper to mint a long-lived Instagram access token.

You only run this when first connecting the account (or if a token ever lapses).
After that, the daily sync refreshes the token automatically (see
birds.scheduled_sync).

Prereqs (see birds/README.md):
  - @birdsofnorthandover is a Professional (Business/Creator) account
  - A Meta app with the "Instagram API with Instagram Login" product
  - Its Instagram App ID + App Secret, and a redirect URI you configured

Set these (or pass as flags):
    export IG_APP_ID=...
    export IG_APP_SECRET=...
    export IG_REDIRECT_URI=https://www.scott-ouellette.com/   # must match the app config

Usage:
    # 1. Print the authorize URL, open it, approve, copy the ?code=... from the redirect
    python auth.py url

    # 2. Exchange that code for a long-lived (~60 day) token
    python auth.py exchange --code PASTE_CODE_HERE

    # ...add --save-ssm to write it straight to SSM Parameter Store:
    python auth.py exchange --code PASTE_CODE_HERE --save-ssm
"""

import argparse
import os
import sys
import urllib.parse

import requests

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
SHORT_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
LONG_TOKEN_URL = "https://graph.instagram.com/access_token"
SCOPE = "instagram_business_basic"


def _cfg(args):
    app_id = args.app_id or os.environ.get("IG_APP_ID")
    secret = args.app_secret or os.environ.get("IG_APP_SECRET")
    redirect = args.redirect_uri or os.environ.get("IG_REDIRECT_URI")
    missing = [
        name
        for name, val in [
            ("IG_APP_ID", app_id),
            ("IG_APP_SECRET", secret),
            ("IG_REDIRECT_URI", redirect),
        ]
        if not val
    ]
    if missing:
        sys.exit("Missing required config: {} (set env vars or pass flags)".format(", ".join(missing)))
    return app_id, secret, redirect


def cmd_url(args):
    app_id, _, redirect = _cfg(args)
    params = {
        "client_id": app_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": SCOPE,
    }
    print("\nOpen this URL, approve the @birdsofnorthandover account, then copy the")
    print("`code` parameter from the URL you get redirected to:\n")
    print(AUTHORIZE_URL + "?" + urllib.parse.urlencode(params) + "\n")


def cmd_exchange(args):
    app_id, secret, redirect = _cfg(args)
    code = args.code.strip()
    # Instagram appends "#_" to the redirected code; strip it if pasted.
    code = code.split("#")[0]

    # 1) code -> short-lived token (+ user id)
    short = requests.post(
        SHORT_TOKEN_URL,
        data={
            "client_id": app_id,
            "client_secret": secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
            "code": code,
        },
        timeout=30,
    )
    if not short.ok:
        sys.exit("Short-token exchange failed: {} {}".format(short.status_code, short.text))
    short_data = short.json()
    short_token = short_data["access_token"]
    user_id = short_data.get("user_id")

    # 2) short-lived -> long-lived (~60 days)
    long = requests.get(
        LONG_TOKEN_URL,
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": secret,
            "access_token": short_token,
        },
        timeout=30,
    )
    if not long.ok:
        sys.exit("Long-token exchange failed: {} {}".format(long.status_code, long.text))
    long_data = long.json()
    token = long_data["access_token"]
    expires_days = round((long_data.get("expires_in") or 0) / 86400, 1)

    print("\n✅ Long-lived token (expires in ~{} days):\n".format(expires_days))
    print(token)
    print("\nInstagram user id:", user_id)

    if args.save_ssm:
        import birds

        param = os.environ.get("INSTAGRAM_TOKEN_SSM_PARAM", birds.SSM_TOKEN_PARAM)
        if birds._ssm_put(param, token):
            print("\n💾 Saved to SSM Parameter Store:", param)
        else:
            sys.exit("\nFailed to write to SSM (check AWS creds / permissions).")
    else:
        print("\nNext: store it (either) ...")
        print("  python auth.py exchange --code ... --save-ssm   # write to SSM")
        print("  INSTAGRAM_ACCESS_TOKEN={}  python birds.py       # one-off local sync".format("<token>"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app-id")
    parser.add_argument("--app-secret")
    parser.add_argument("--redirect-uri")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("url", help="print the authorization URL")

    ex = sub.add_parser("exchange", help="exchange an auth code for a long-lived token")
    ex.add_argument("--code", required=True, help="the ?code=... value from the redirect")
    ex.add_argument("--save-ssm", action="store_true", help="store the token in SSM Parameter Store")

    args = parser.parse_args()
    {"url": cmd_url, "exchange": cmd_exchange}[args.command](args)


if __name__ == "__main__":
    main()

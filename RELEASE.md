# Release runbook

Deploying the site (Flask + Zappa on AWS Lambda) and the bird gallery's S3 cache.
Run these from the repo root with your AWS credentials configured. One-time steps
are marked **(once)**.

## 0. Tooling **(once)**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # Flask, Zappa, etc.
# AWS CLI + creds:
brew install awscli
aws configure                              # access key / secret / region us-east-1
```

## 1. Dedicated S3 bucket for bird images + manifest **(once)**

A separate, public-read bucket (NOT the Zappa deploy bucket). No dots in the name
— the image URLs are `https://<bucket>.s3.amazonaws.com/...` and dots break TLS.

```bash
aws s3 mb s3://birds-scott-ouellette --region us-east-1

# Allow public read of the bird assets (just photos + a manifest, nothing secret):
aws s3api put-public-access-block --bucket birds-scott-ouellette \
  --public-access-block-configuration BlockPublicpolicy=false,RestrictPublicBuckets=false,BlockPublicAcls=true,IgnorePublicAcls=true

aws s3api put-bucket-policy --bucket birds-scott-ouellette --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadBirds",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::birds-scott-ouellette/birds/*"
  }]
}'
```

If you pick a different bucket name, update `BIRDS_S3_BUCKET` and the
`extra_permissions` ARN in `zappa_settings.json` to match.

## 2. Instagram token into SSM **(once, refreshes itself after)**

```bash
# Mint a token (see birds/README.md) and store it as a SecureString:
python auth.py exchange --code <CODE> --save-ssm
# or migrate the local dev token:
aws ssm put-parameter --name /birds/instagram_token --type SecureString \
  --value "$(cat .ig_token)" --overwrite
```

The daily `birds.scheduled_sync` Lambda refreshes it automatically thereafter.

## 3. Deploy

```bash
zappa update production      # (first time on a fresh account: zappa deploy production)
```

## 4. Populate the gallery cache

The committed `birds/manifest.json` uses Instagram URLs that expire, so run one
sync to re-host images into S3 and write the live manifest:

```bash
zappa invoke production 'birds.scheduled_sync'
# verify:
aws s3 ls s3://birds-scott-ouellette/birds/images/ | head
```

## 5. Bird subdomain `birds.scott-ouellette.com` **(once)**

```bash
zappa certify production     # provisions ACM cert + API Gateway custom domain
# then add a Route 53 alias/CNAME: birds.scott-ouellette.com -> the API Gateway domain
```

## Rollback

```bash
zappa rollback production -n 1
```

## Notes
- `.ig_token` is gitignored — never committed.
- Like counts are never stored or shown; only a 0–1 popularity weight.
- Curation lives in `birds/excluded.json` and is respected by every sync.

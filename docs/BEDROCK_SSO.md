# Bedrock via AWS SSO — provider adapter

`src/product_forge/agents/bedrock_provider.py` maps the PF gateway
subprocess contract onto `bedrock-runtime: Converse` using **AWS SSO
(IAM Identity Center)** credentials — never static keys.

## Setup (operator steps — cannot be automated)

```bash
# 1. AWS CLI v2 (required for the SSO browser flow)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp && /tmp/aws/install --update

# 2. ~/.aws/config — sso-session profile (values from your IdC admin)
cat >> ~/.aws/config <<'EOF'
[sso-session forge]
sso_start_url = https://<your-idc>.awsapps.com/start
sso_region = us-east-1
sso_registration_scopes = sso:account:access
[profile bedrock]
sso_session = forge
sso_account_id = <account-id>
sso_role_name = <role-with-bedrock:InvokeModel>
region = us-east-1
EOF

# 3. login (opens browser — human step)
aws sso login --profile bedrock

# 4. wire PF gateway (productforge config / workspace config)
#    gateway.provider_cmd = ["python", "-m", "product_forge.agents.bedrock_provider"]
export PF_BEDROCK_PROFILE=bedrock
export PF_BEDROCK_REGION=us-east-1
export PF_BEDROCK_MODEL=anthropic.claude-3-7-sonnet-20250219-v1:0
```

## Honest states (verified live on this host)

| Condition | State emitted |
|---|---|
| boto3 absent | `unavailable:dependency` (exit 3) |
| profile missing | `unavailable:no-profile` (exit 4) |
| no/expired SSO session | `unverified:no-sso-session` (exit 5) |
| AWS error (AccessDenied, ValidationException…) | `unavailable:<aws-code>` (exit 6) |
| success | `{text, model, usage, stop_reason}` |

Verified on this host: `unavailable:dependency` → after
`uv pip install boto3` → `unverified:no-sso-session` (no `~/.aws` exists).
A real `converse` call remains **unverified** until steps 1–3 are done —
this adapter never fabricates a response.

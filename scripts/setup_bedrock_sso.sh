#!/usr/bin/env bash
# Scaffold ~/.aws/config for AWS SSO (Identity Center) → Bedrock, then login.
# Usage: ./scripts/setup_bedrock_sso.sh   (prompts for IdC values)
set -euo pipefail
read -rp "SSO start URL (https://<idc>.awsapps.com/start): " URL
read -rp "SSO region [us-east-1]: " SR; SR=${SR:-us-east-1}
read -rp "Account ID: " ACCT
read -rp "Role name (needs bedrock:InvokeModel): " ROLE
read -rp "Bedrock region [us-east-1]: " BR; BR=${BR:-us-east-1}
cat >> ~/.aws/config <<CFG
[sso-session forge]
sso_start_url = $URL
sso_region = $SR
sso_registration_scopes = sso:account:access
[profile bedrock]
sso_session = forge
sso_account_id = $ACCT
sso_role_name = $ROLE
region = $BR
CFG
echo "profile 'bedrock' written. Logging in (browser opens)…"
aws sso login --profile bedrock
aws sts get-caller-identity --profile bedrock
echo 'export PF_BEDROCK_PROFILE=bedrock'
echo "gateway.provider_cmd = [\"python\",\"-m\",\"product_forge.agents.bedrock_provider\"]"

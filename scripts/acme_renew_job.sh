#!/usr/bin/env bash
# 每天由 cron 调用；acme.sh 仅在临期(约30天内)时才真正续期，其余为 no-op
set -a
source /home/admin/workboard/config/aliyun_dns.env
set +a
export Ali_Key="$ALI_KEY" Ali_Secret="$ALI_SECRET"
/home/admin/.acme.sh/acme.sh --renew -d 2566.online --ecc >> /var/log/acme_renew.log 2>&1

"""Patch service.py to add progressive lockout logic."""
from time import monotonic

p = "/app/app/services/auth/service.py"
with open(p, "r") as f:
    c = f.read()

# Add monotonic import if missing
if "from time import monotonic" not in c:
    c = c.replace("import uuid\n", "import uuid\nfrom time import monotonic\n")

# Add lockout check before IP limit
old_start = """    user = await _find_user_by_identifier(db, identifier)
    if user is None or not verify_password(password, user.password_hash):
        # IP 维度限流"""

new_start = """    user = await _find_user_by_identifier(db, identifier)
    if user is None or not verify_password(password, user.password_hash):
        # 渐进式锁定期检查
        lockout_key = _rate_limit_key(ip, identifier)
        remaining = _lockout_remaining(lockout_key, now=monotonic())
        if remaining > 0:
            mins = remaining // 60
            secs = remaining % 60
            msg = f"登录失败次数过多，请 {mins} 分 {secs} 秒后再试" if mins else f"登录失败次数过多，请 {secs} 秒后再试"
            raise RateLimitError(msg)

        # IP 维度限流"""

c = c.replace(old_start, new_start)

# Replace the rate limit block with lockout-aware version
old_block = """        if is_login_rate_limited(ip, identifier):
            await write_audit_log(
                db,
                action="auth.login_rate_limited",
                metadata={"identifier": identifier.strip()},
                ip=ip,
            )
            await db.commit()
            raise RateLimitError("登录失败次数过多，请 15 分钟后再试")"""

new_block = """        if is_login_rate_limited(ip, identifier):
            lockout_key = _rate_limit_key(ip, identifier)
            record_lockout_strike(lockout_key)
            remaining = _lockout_remaining(lockout_key)
            mins = remaining // 60
            secs = remaining % 60
            msg = f"登录失败次数过多，请 {mins} 分 {secs} 秒后再试" if mins else f"登录失败次数过多，请 {secs} 秒后再试"
            await write_audit_log(
                db,
                action="auth.login_rate_limited",
                metadata={"identifier": identifier.strip(), "lockout_seconds": remaining},
                ip=ip,
            )
            await db.commit()
            raise RateLimitError(msg)"""

c = c.replace(old_block, new_block)

with open(p, "w") as f:
    f.write(c)
print("OK")

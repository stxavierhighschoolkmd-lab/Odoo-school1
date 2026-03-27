# Copy this file to ~/.config/firejail
#
# Firejail profile for Claude Code.
#
# Provides filesystem isolation so Claude can only access explicitly
# whitelisted directories. It is intended to run Claude in standalone.
#
# Usage:
#   firejail --profile=claude.profile --whitelist=~/src/odoo claude
#
# LIMITATIONS
#   Firejail always creates a PID namespace, which prevents VSCode IDE
#   integration (`claude /ide`).
#   Use bwrap-claude.sh or the provided code.local if you need the feature.

# ============================================================================
# SECURITY HARDENING
# ============================================================================

caps.drop all
nonewprivs
noroot
seccomp

nodvd
nosound
no3d
notv
nou2f
novideo
nogroups

# ============================================================================
# FILESYSTEM ISOLATION
# ============================================================================

# Override blacklists from the includes below for paths we need.
# noblacklist must appear before the include that would blacklist the path.
noblacklist ${HOME}/.cache/claude
noblacklist ${HOME}/.cache/claude-cli-nodejs
noblacklist ${HOME}/.claude
noblacklist ${HOME}/.claude.json
noblacklist ${HOME}/.local/bin/claude
noblacklist ${HOME}/.local/share/claude
noblacklist ${HOME}/.local/state/claude

include disable-common.inc
include disable-programs.inc

private-tmp
private-dev
private-etc alternatives,ca-certificates,host.conf,hostname,hosts,ld.so.cache,ld.so.conf,ld.so.conf.d,ld.so.preload,localtime,login.defs,nsswitch.conf,passwd,resolv.conf,ssl

disable-mnt

# ============================================================================
# WHITELIST - WRITABLE PATHS
# ============================================================================

mkdir ${HOME}/.cache/claude
mkdir ${HOME}/.cache/claude-cli-nodejs
mkdir ${HOME}/.claude
mkdir ${HOME}/.local/state/claude

whitelist ${HOME}/.cache/claude
whitelist ${HOME}/.cache/claude-cli-nodejs
whitelist ${HOME}/.claude
whitelist ${HOME}/.claude.json
whitelist ${HOME}/.local/bin/claude
whitelist ${HOME}/.local/share/claude
whitelist ${HOME}/.local/state/claude

# ============================================================================
# NETWORK
# ============================================================================

# Network access is REQUIRED for Claude API calls.
# Do not add: net none

# ============================================================================
# D-BUS
# ============================================================================

dbus-user none
dbus-system none

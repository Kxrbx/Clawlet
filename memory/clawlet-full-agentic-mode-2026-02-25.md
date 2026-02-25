# Full Agentic Mode Notes (safe vs full_exec)

This branch introduces explicit runtime intent for machine-level autonomy:

- `agent.mode: safe | full_exec`
- `agent.shell_allow_dangerous: bool`

## Mode behavior

### safe (default)
- File tools restricted to workspace `allowed_dir`
- Shell tool runs in workspace context
- Shell dangerous patterns remain blocked unless explicitly overridden

### full_exec
- File tools are not restricted by `allowed_dir` (machine-wide scope)
- Shell runs without workspace restriction
- Shell whitelist is expanded with additional machine-ops commands:
  - mkdir, cp, mv, rm, touch, chmod, chown
  - curl, wget, ssh, scp, rsync
  - make, docker, kubectl, terraform
- Optional `agent.shell_allow_dangerous=true` can disable dangerous-pattern blocking

## Caution

`full_exec` intentionally increases capability and risk. Only run in trusted environments.

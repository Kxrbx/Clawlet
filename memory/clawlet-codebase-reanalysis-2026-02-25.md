# Clawlet Codebase Reanalysis (Bugs, Risks, Optimizations)

Date: 2026-02-25

## Scope
- Re-reviewed core runtime (`agent/loop.py`, `tools/registry.py`, `tools/files.py`), config/onboarding flow, and init templates.
- Focused on correctness, long-session stability, Python compatibility, and config/tooling drift.

## Issues found and fixed

1. Python 3.10 compatibility risk
- `datetime.UTC` import can break on 3.10 runtime.
- Fix: switched to `datetime.timezone.utc` constant alias (`UTC_TZ`) in agent loop.

2. Tool failure telemetry overcount
- Tool failures could be incremented twice for one exception path.
- Fix: removed duplicate increment in exception branch and retained failure accounting in unified failure block.

3. Schema validation accepted unknown parameters by default
- Tool schema validation did not reject extra args when schema intended strict shape.
- Fix: added support for `additionalProperties: false` and reject unknown params.

4. Onboarding step indicator drift
- Step list expanded but early step indicators still used old totals.
- Fix: aligned onboarding step counters to 7-step flow.

5. Config/onboarding mismatch
- Onboarding wrote `web_search` and used `Config.save()`, while config model lacked `web_search` field and save alias.
- Fix: added `web_search` to `Config` and `Config.save()` alias to `to_yaml()`.

6. Init template drift with new execution mode
- `init` templates lacked `agent.mode` and `agent.shell_allow_dangerous` keys.
- Fix: added keys to both template generators and corrected malformed channel YAML indentation in command init template.

## Added test guards
- `test_validate_tool_params_rejects_unknown_when_additional_properties_false`
- `test_agent_loop_module_imports_on_python_310_compat_path`
- `test_init_config_template_is_valid_yaml_and_includes_agent_mode`

## Remaining recommendations (not changed in this patch)
- Add per-chat/session state isolation in `AgentLoop` to avoid shared-history coupling.
- Add token-budget based context pruning/summarization (not just message-count windows).
- Add stricter policy gates for full machine execution mode (approval hooks or safety prompts).

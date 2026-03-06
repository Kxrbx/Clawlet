"""
Tests for metrics module.
"""

def test_metrics_counters():
    from clawlet.metrics import get_metrics, reset_metrics
    
    reset_metrics()
    m = get_metrics()
    
    assert m.messages_total == 0
    assert m.errors_total == 0
    
    m.inc_messages()
    assert m.messages_total == 1
    
    m.inc_errors()
    assert m.errors_total == 1
    m.inc_scheduled_runs_attempted()
    m.inc_scheduled_runs_succeeded()
    m.inc_scheduled_runs_failed()
    m.inc_proactive_tasks_completed()
    assert m.scheduled_runs_attempted_total == 1
    assert m.scheduled_runs_succeeded_total == 1
    assert m.scheduled_runs_failed_total == 1
    assert m.proactive_tasks_completed_total == 1
    
    # Uptime should be > 0
    assert m.uptime_seconds >= 0

def test_metrics_prometheus_format():
    from clawlet.metrics import get_metrics, reset_metrics, format_prometheus
    
    reset_metrics()
    m = get_metrics()
    m.inc_messages()
    m.inc_messages()
    m.inc_errors()
    
    output = format_prometheus()
    
    assert "clawlet_messages_total 2" in output
    assert "clawlet_errors_total 1" in output
    assert "clawlet_scheduled_runs_attempted_total" in output
    assert "clawlet_proactive_tasks_completed_total" in output
    assert "clawlet_uptime_seconds" in output
    assert output.count("\n") >= 4  # au moins 4 lignes

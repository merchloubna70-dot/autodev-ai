"""Replay timeline HTML renderer.

Reads `.dev-factory/runs/<run_id>/execution/execution_calls.jsonl` and emits
a single self-contained HTML page with a horizontal scrubber, a side panel
showing per-step content, and color-coded lanes by ``backend`` field.

Pure stdlib — no external assets, no CDN scripts.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

# Deterministic colour palette keyed by backend name (cycles for unknowns)
_LANE_COLOURS: list[str] = [
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ac",
]


def _colour_for(backend: str, registry: dict[str, str]) -> str:
    if backend not in registry:
        idx = len(registry) % len(_LANE_COLOURS)
        registry[backend] = _LANE_COLOURS[idx]
    return registry[backend]


def _load_steps(jsonl_path: Path) -> list[dict]:
    steps: list[dict] = []
    if not jsonl_path.exists():
        return steps
    with jsonl_path.open(encoding="utf-8") as fh:
        for idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                obj = {"raw": line}
            obj.setdefault("step_index", idx)
            obj.setdefault("backend", "unknown")
            obj.setdefault("task_id", f"step-{idx}")
            obj.setdefault("timestamp", "")
            obj.setdefault("success", True)
            obj.setdefault("duration_ms", 0)
            obj.setdefault("summary", "")
            steps.append(obj)
    return steps


def _steps_js(steps: list[dict]) -> str:
    """Serialize steps for inline JS."""
    return json.dumps(steps, ensure_ascii=False)


def _legend_html(colour_map: dict[str, str]) -> str:
    parts = []
    for backend, colour in colour_map.items():
        swatch = (
            f'<span style="display:inline-block;width:12px;height:12px;'
            f'background:{colour};border-radius:2px;margin-right:4px;"></span>'
        )
        parts.append(f"<span style='margin-right:12px;'>{swatch}{html.escape(backend)}</span>")
    return "".join(parts)


class ReplayTimelineRenderer:
    """Render a self-contained HTML replay page for a factory run."""

    def render_html(self, run_id: str, repo_path: str) -> str:
        """Return a single-file HTML string for the given run.

        Parameters
        ----------
        run_id:
            The run identifier (directory name under ``.dev-factory/runs/``).
        repo_path:
            Absolute path to the repository root.
        """
        jsonl_path = (
            Path(repo_path)
            / ".dev-factory"
            / "runs"
            / run_id
            / "execution"
            / "execution_calls.jsonl"
        )
        steps = _load_steps(jsonl_path)

        colour_map: dict[str, str] = {}
        for step in steps:
            _colour_for(step.get("backend", "unknown"), colour_map)

        legend = _legend_html(colour_map)
        steps_js = _steps_js(steps)
        total = max(len(steps) - 1, 0)
        run_id_escaped = html.escape(run_id)

        # Build a compact dot timeline for each step
        dots_html_parts: list[str] = []
        for i, step in enumerate(steps):
            colour = colour_map.get(step.get("backend", "unknown"), "#999")
            ok = step.get("success", True)
            border = "2px solid #fff" if ok else "2px solid #ff0000"
            dots_html_parts.append(
                f'<span class="dot" data-idx="{i}" '
                f'style="background:{colour};border:{border};" '
                f'title="{html.escape(step.get("task_id",""))}"></span>'
            )
        dots_html = "".join(dots_html_parts)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Replay: {run_id_escaped}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }}
header {{ padding: 12px 20px; background: #16213e; border-bottom: 1px solid #0f3460; }}
header h1 {{ font-size: 1rem; font-weight: 600; color: #e0e0ff; }}
header .legend {{ margin-top: 6px; font-size: 0.75rem; color: #aaa; }}
.scrubber-bar {{ padding: 10px 20px; background: #16213e; border-bottom: 1px solid #0f3460; display: flex; align-items: center; gap: 12px; }}
#scrubber {{ flex: 1; accent-color: #4e79a7; }}
#step-counter {{ font-size: 0.8rem; color: #aaa; min-width: 80px; text-align: right; }}
.timeline {{ padding: 8px 20px; background: #0d1b2a; border-bottom: 1px solid #0f3460; min-height: 36px; display: flex; flex-wrap: wrap; align-items: center; gap: 3px; }}
.dot {{ display: inline-block; width: 14px; height: 14px; border-radius: 50%; cursor: pointer; transition: transform .1s; }}
.dot:hover, .dot.active {{ transform: scale(1.4); }}
.content-area {{ flex: 1; overflow: auto; display: flex; }}
.panel {{ flex: 1; padding: 16px 20px; overflow: auto; }}
.panel h2 {{ font-size: 0.9rem; color: #7ecfff; margin-bottom: 8px; }}
.panel pre {{ background: #0f1e32; border-radius: 6px; padding: 12px; font-size: 0.78rem; white-space: pre-wrap; word-break: break-word; color: #c9d1d9; border: 1px solid #21395a; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 600; margin-right: 6px; }}
.badge-ok {{ background: #2ea04333; color: #2ea043; }}
.badge-fail {{ background: #f8514933; color: #f85149; }}
</style>
</head>
<body>
<header>
  <h1>Run replay &mdash; <code>{run_id_escaped}</code></h1>
  <div class="legend">{legend}</div>
</header>
<div class="scrubber-bar">
  <label for="scrubber" style="font-size:.8rem;color:#aaa;white-space:nowrap;">Step</label>
  <input type="range" id="scrubber" min="0" max="{total}" value="0" step="1"/>
  <span id="step-counter">0 / {total}</span>
</div>
<div class="timeline" id="dot-row">
{dots_html}
</div>
<div class="content-area">
  <div class="panel" id="detail-panel">
    <h2>Select a step to view details</h2>
    <pre id="detail-pre">No data</pre>
  </div>
</div>
<script>
(function() {{
  var steps = {steps_js};
  var scrubber = document.getElementById('scrubber');
  var counter  = document.getElementById('step-counter');
  var detPre   = document.getElementById('detail-pre');
  var detH2    = document.querySelector('#detail-panel h2');
  var dots     = Array.from(document.querySelectorAll('.dot'));
  var total    = {total};

  function renderStep(idx) {{
    idx = Math.max(0, Math.min(idx, steps.length - 1));
    scrubber.value = idx;
    counter.textContent = idx + ' / ' + total;
    dots.forEach(function(d, i) {{ d.classList.toggle('active', i === idx); }});
    if (steps.length === 0) {{
      detH2.textContent = 'No steps recorded';
      detPre.textContent = '';
      return;
    }}
    var s = steps[idx] || {{}};
    var ok = s.success !== false;
    var badge = ok
      ? '<span class="badge badge-ok">OK</span>'
      : '<span class="badge badge-fail">FAIL</span>';
    detH2.innerHTML = badge + 'Step ' + (s.step_index !== undefined ? s.step_index : idx)
      + ' &mdash; ' + (s.task_id || '') + ' &nbsp; <span style="color:#7ecfff;font-size:.8rem;">' + (s.backend || '') + '</span>';
    detPre.textContent = JSON.stringify(s, null, 2);
  }}

  scrubber.addEventListener('input', function() {{ renderStep(parseInt(this.value, 10)); }});
  dots.forEach(function(d, i) {{
    d.addEventListener('click', function() {{ renderStep(i); }});
  }});
  renderStep(0);
}})();
</script>
</body>
</html>"""

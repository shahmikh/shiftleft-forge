"""
ShiftLeft Forge - Findings Aggregator
Reads SARIF output from multiple scanners and produces
one plain-English summary, ranked by severity.
"""
import json
import sys
from pathlib import Path
 
SEVERITY_ORDER = {"error": 3, "warning": 2, "note": 1}
 
def load_sarif(path: str) -> list[dict]:
    if not Path(path).exists():
        return []
    data = json.loads(Path(path).read_text())
    findings = []
    for run in data.get('runs', []):
        tool_name = run.get('tool', {}).get('driver', {}).get('name', 'unknown')
        for result in run.get('results', []):
            findings.append({
                'tool': tool_name,
                'rule': result.get('ruleId', 'unknown-rule'),
                'level': result.get('level', 'warning'),
                'message': result.get('message', {}).get('text', ''),
                'location': _get_location(result),
            })
    return findings
 
def _get_location(result: dict) -> str:
    try:
        loc = result['locations'][0]['physicalLocation']
        return f"{loc['artifactLocation']['uri']}:{loc.get('region', {}).get('startLine', '?')}"
    except (KeyError, IndexError):
        return 'unknown location'
 
def build_summary(all_findings: list[dict]) -> str:
    all_findings.sort(key=lambda f: SEVERITY_ORDER.get(f['level'], 0), reverse=True)
    critical = [f for f in all_findings if f['level'] == 'error']
    warning  = [f for f in all_findings if f['level'] == 'warning']
 
    lines = ["## ShiftLeft Forge - Security Scan Summary\n"]
    lines.append(f"Total findings: {len(all_findings)} "
                  f"({len(critical)} critical, {len(warning)} warning)\n")
 
    if not all_findings:
        lines.append('No findings across all security layers.')
        return '\n'.join(lines)
 
    if critical:
        lines.append('### CRITICAL - must fix before merge')
        for f in critical[:10]:
            lines.append(f"- [{f['tool']}] {f['rule']} at {f['location']} - {f['message']}")
 
    if warning:
        lines.append('\n### Warnings - review recommended')
        for f in warning[:10]:
            lines.append(f"- [{f['tool']}] {f['rule']} at {f['location']} - {f['message']}")
 
    return '\n'.join(lines)
 
def main():
    sarif_files = sys.argv[1:]
    all_findings = []
    for f in sarif_files:
        all_findings.extend(load_sarif(f))
 
    summary = build_summary(all_findings)
    print(summary)
    Path('pr-summary.md').write_text(summary)
 
    if any(f['level'] == 'error' for f in all_findings):
        sys.exit(1)   # This is the real deploy gate
    sys.exit(0)
 
if __name__ == '__main__':
    main()
 

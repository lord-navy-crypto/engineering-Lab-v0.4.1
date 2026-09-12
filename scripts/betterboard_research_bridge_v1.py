#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

SCHEMA = 'betterboard.research-bridge/1.0'
REQUIRED_TOP = {
    'schema', 'session_id', 'created_at_utc', 'producer', 'experiment', 'hardware',
    'evidence', 'research_context', 'engineering_lab', 'ai', 'provenance'
}
ALLOWED_ORIGINS = {'human', 'betterboard', 'engineering-lab', 'openguin'}
ALLOWED_KINDS = {
    'observation', 'measurement', 'analysis', 'annotation', 'hypothesis',
    'suggestion', 'warning', 'decision'
}


def load_bridge(path: Path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Bridge root must be a JSON object')
    return value


def validate_event(event, location):
    if not isinstance(event, dict):
        raise ValueError(f'{location} event must be an object')
    origin = event.get('origin')
    kind = event.get('kind')
    if origin not in ALLOWED_ORIGINS:
        raise ValueError(f'{location} has unsupported origin: {origin!r}')
    if kind not in ALLOWED_KINDS:
        raise ValueError(f'{location} has unsupported kind: {kind!r}')
    if not str(event.get('text', '')).strip():
        raise ValueError(f'{location} event has no text')


def validate_bridge(value):
    missing = sorted(REQUIRED_TOP - set(value))
    if missing:
        raise ValueError('Missing required field(s): ' + ', '.join(missing))
    if value.get('schema') != SCHEMA:
        raise ValueError(f'Unsupported schema: {value.get("schema")!r}')
    if not str(value.get('session_id', '')).strip():
        raise ValueError('session_id must be non-empty')

    evidence = value.get('evidence')
    if not isinstance(evidence, dict):
        raise ValueError('evidence must be an object')
    if not isinstance(evidence.get('sample_count'), int) or evidence['sample_count'] < 0:
        raise ValueError('evidence.sample_count must be a non-negative integer')
    for key in ('data_csv', 'metadata_json'):
        if not str(evidence.get(key, '')).strip():
            raise ValueError(f'evidence.{key} must be present')

    context = value.get('research_context')
    if not isinstance(context, dict):
        raise ValueError('research_context must be an object')
    for name in ('notebook', 'annotations', 'lab_journey'):
        events = context.get(name, [])
        if not isinstance(events, list):
            raise ValueError(f'research_context.{name} must be an array')
        for index, event in enumerate(events):
            validate_event(event, f'research_context.{name}[{index}]')

    engineering = value.get('engineering_lab')
    if not isinstance(engineering, dict):
        raise ValueError('engineering_lab must be an object')
    for name in ('imports', 'results'):
        events = engineering.get(name, [])
        if not isinstance(events, list):
            raise ValueError(f'engineering_lab.{name} must be an array')
        for index, event in enumerate(events):
            validate_event(event, f'engineering_lab.{name}[{index}]')

    ai = value.get('ai')
    if not isinstance(ai, dict):
        raise ValueError('ai must be an object')
    if ai.get('provider') != 'OpenPenguin':
        raise ValueError('ai.provider must remain OpenPenguin for this bridge version')
    suggestions = ai.get('suggestions', [])
    if not isinstance(suggestions, list):
        raise ValueError('ai.suggestions must be an array')
    for index, event in enumerate(suggestions):
        validate_event(event, f'ai.suggestions[{index}]')

    provenance = value.get('provenance')
    if not isinstance(provenance, list) or not provenance:
        raise ValueError('provenance must contain at least one event')
    for index, event in enumerate(provenance):
        validate_event(event, f'provenance[{index}]')


def main():
    parser = argparse.ArgumentParser(description='Validate BetterBoard Research Bridge v1 before Engineering Lab import.')
    parser.add_argument('bridge', type=Path)
    parser.add_argument('--summary-json', action='store_true')
    args = parser.parse_args()

    value = load_bridge(args.bridge)
    validate_bridge(value)
    summary = {
        'status': 'PASS',
        'schema': value['schema'],
        'session_id': value['session_id'],
        'experiment': value.get('experiment', {}).get('title'),
        'samples': value['evidence']['sample_count'],
        'notebook_entries': len(value['research_context'].get('notebook', [])),
        'annotations': len(value['research_context'].get('annotations', [])),
        'journey_events': len(value['research_context'].get('lab_journey', [])),
        'engineering_results': len(value['engineering_lab'].get('results', [])),
        'ai_suggestions': len(value['ai'].get('suggestions', [])),
    }
    if args.summary_json:
        print(json.dumps(summary, indent=2))
    else:
        print('BetterBoard Research Bridge v1: PASS')
        print(f"- session: {summary['session_id']}")
        print(f"- experiment: {summary['experiment']}")
        print(f"- samples: {summary['samples']}")
        print('- raw measurement remains evidence; Engineering Lab and OpenPenguin records stay derived/advisory')


if __name__ == '__main__':
    main()

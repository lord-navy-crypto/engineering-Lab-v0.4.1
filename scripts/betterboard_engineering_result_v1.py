#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import uuid

BRIDGE_SCHEMA = 'betterboard.research-bridge/1.0'
RESULT_SCHEMA = 'engineering-lab.result/1.0'
ALLOWED_KINDS = {'analysis', 'warning', 'decision'}


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_json(path: Path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('JSON root must be an object')
    return value


def validate_bridge(bridge):
    if bridge.get('schema') != BRIDGE_SCHEMA:
        raise ValueError(f'Unsupported BetterBoard bridge schema: {bridge.get("schema")!r}')
    session_id = str(bridge.get('session_id', '')).strip()
    if not session_id:
        raise ValueError('BetterBoard bridge has no session_id')
    evidence = bridge.get('evidence')
    if not isinstance(evidence, dict) or not str(evidence.get('metadata_json', '')).strip():
        raise ValueError('BetterBoard bridge does not contain traceable measurement metadata')
    return session_id


def make_event(kind, text, refs):
    if kind not in ALLOWED_KINDS:
        raise ValueError(f'Unsupported Engineering Lab result kind: {kind}')
    text = text.strip()
    if not text:
        raise ValueError('Result text must be non-empty')
    if len(text) > 12000:
        raise ValueError('Result text exceeds 12000 characters')
    created = utc_now()
    return {
        'id': f'engineering-lab:{kind}:{uuid.uuid4().hex}',
        'created_at_utc': created,
        'origin': 'engineering-lab',
        'kind': kind,
        'text': text,
        'refs': [str(ref)[:2000] for ref in refs[:20]],
    }


def validate_result_envelope(value, expected_session=None):
    if value.get('schema') != RESULT_SCHEMA:
        raise ValueError(f'Unsupported result schema: {value.get("schema")!r}')
    if value.get('source_bridge_schema') != BRIDGE_SCHEMA:
        raise ValueError('Result envelope source_bridge_schema is incompatible')
    session_id = str(value.get('session_id', '')).strip()
    if not session_id:
        raise ValueError('Result envelope session_id is missing')
    if expected_session and session_id != expected_session:
        raise ValueError('Result envelope belongs to a different BetterBoard session')
    results = value.get('results')
    if not isinstance(results, list) or not 1 <= len(results) <= 500:
        raise ValueError('Result envelope must contain 1..500 result events')
    for index, event in enumerate(results):
        if not isinstance(event, dict):
            raise ValueError(f'Result event {index + 1} must be an object')
        if event.get('origin') != 'engineering-lab':
            raise ValueError(f'Result event {index + 1} must use origin=engineering-lab')
        if event.get('kind') not in ALLOWED_KINDS:
            raise ValueError(f'Result event {index + 1} cannot impersonate raw measurement or AI/human context')
        if not str(event.get('id', '')).strip() or not str(event.get('text', '')).strip():
            raise ValueError(f'Result event {index + 1} is incomplete')
    return session_id


def main():
    parser = argparse.ArgumentParser(description='Create or validate an Engineering Lab result envelope for a BetterBoard Research Bridge v1 session.')
    parser.add_argument('--bridge', type=Path, help='BetterBoard Research Bridge JSON used as the source session')
    parser.add_argument('--kind', choices=sorted(ALLOWED_KINDS), default='analysis')
    parser.add_argument('--text', help='Derived Engineering Lab result text')
    parser.add_argument('--ref', action='append', default=[], help='Derived artifact reference; may be repeated')
    parser.add_argument('--output', type=Path, help='Write the result envelope JSON here')
    parser.add_argument('--validate', type=Path, help='Validate an existing Engineering Lab result envelope')
    parser.add_argument('--capabilities-json', action='store_true', help='Print this tool interoperability capabilities')
    args = parser.parse_args()

    if args.capabilities_json:
        print(json.dumps({
            'producer': 'Engineering Lab',
            'accepts_bridge_schema': BRIDGE_SCHEMA,
            'produces_result_schema': RESULT_SCHEMA,
            'result_kinds': sorted(ALLOWED_KINDS),
            'policies': {
                'raw_measurement_immutable': True,
                'derived_results_only': True,
                'session_match_required': True,
            },
        }, indent=2))
        return

    if args.validate:
        value = load_json(args.validate)
        expected = validate_bridge(load_json(args.bridge)) if args.bridge else None
        session_id = validate_result_envelope(value, expected)
        print(f'Engineering Lab result envelope: PASS\n- session: {session_id}\n- results: {len(value["results"])}')
        return

    if not args.bridge or not args.text or not args.output:
        parser.error('--bridge, --text, and --output are required when creating a result envelope')

    bridge = load_json(args.bridge)
    session_id = validate_bridge(bridge)
    envelope = {
        'schema': RESULT_SCHEMA,
        'source_bridge_schema': BRIDGE_SCHEMA,
        'session_id': session_id,
        'created_at_utc': utc_now(),
        'producer': 'Engineering Lab',
        'results': [make_event(args.kind, args.text, args.ref)],
        'artifacts': [],
        'warnings': [],
    }
    validate_result_envelope(envelope, session_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(envelope, indent=2) + '\n', encoding='utf-8')
    print(f'Engineering Lab result envelope written: {args.output}\n- session: {session_id}\n- schema: {RESULT_SCHEMA}')


if __name__ == '__main__':
    main()

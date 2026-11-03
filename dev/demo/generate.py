"""Fictional public demo producer: stdlib only, deterministic per UTC date.
No athlete account, credentials, external data, network or coaching decisions.
"""
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FILES = ('latest.json', 'history.json', 'intervals.json', 'routes.json',
         'saved_workouts.json', 'ftp_history.json', 'route_eta_history.json')
LABEL = 'FICTIONAL DEMO DATA: generated values, no real person or measurements'


def documents(day):
    if type(day) is not date:
        raise ValueError('demo date must be a calendar date')
    stamp = day.isoformat() + 'T00:00:00Z'
    metadata = {'synthetic': True, 'source': 'section-11-demo deterministic generator',
                'notice': LABEL, 'last_updated': stamp, 'timezone': 'UTC'}
    activities = []
    daily = []
    for offset in range(28):
        when = day - timedelta(days=27 - offset)
        # A repeatable fictional week: two rest days and five indoor rides.
        minutes = (0, 60, 45, 75, 0, 105, 90)[when.weekday()]
        watts = (0, 155, 130, 170, 0, 145, 150)[when.weekday()]
        daily.append({'date': when.isoformat(), 'synthetic': True,
                      'duration_minutes': minutes, 'sleep_hours': 7.5 + (when.toordinal() % 3) * 0.2})
        if minutes:
            activities.append({'id': 'demo-' + when.isoformat(), 'synthetic': True,
                               'name': 'Fictional indoor endurance ride', 'type': 'VirtualRide',
                               'start_date_local': when.isoformat() + 'T08:00:00',
                               'moving_time': minutes * 60, 'average_watts': watts,
                               'average_heartrate': 120 + watts // 10})
    latest = {'READ_THIS_FIRST': {'demo_notice': LABEL,
               'limits': 'Synthetic pipeline example; no real readiness, medical or training recommendation.'},
              'data_overview': {'version': 1, 'managed_files': list(FILES)},
              'metadata': metadata,
              'athlete_profile': {'name': 'Fictional Demo Rider', 'synthetic': True,
                                  'timezone': 'UTC', 'location': None},
              'activities': [a for a in activities if a['start_date_local'][:10] >= (day - timedelta(days=6)).isoformat()],
              'wellness': daily[-7:],
              'fitness_metrics': {'status': 'unavailable', 'reason': 'Demo does not compute physiology'},
              'planned_workouts': []}
    return {
        'latest.json': latest,
        'history.json': {'metadata': metadata, 'daily': daily, 'activities': activities},
        'intervals.json': {'metadata': metadata, 'activities': [], 'reason': 'No synthetic interval streams'},
        'routes.json': {'metadata': metadata, 'events': [], 'reason': 'Indoor demo; no location or route'},
        'saved_workouts.json': {'metadata': metadata, 'workouts': []},
        'ftp_history.json': {'metadata': metadata, 'history': [
            {'date': (day - timedelta(days=27)).isoformat(), 'ftp': 220, 'indoor': True, 'synthetic': True}]},
        'route_eta_history.json': {'metadata': metadata, 'rides': []},
    }


def produce(root, day=None):
    day = day or datetime.now(timezone.utc).date()
    payload = documents(day)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    # Validate all destinations before changing any file.
    for name in payload:
        target = root / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError('demo output must be an ordinary file: ' + name)
    for name, document in payload.items():
        (root / name).write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    print(LABEL + '; UTC date ' + day.isoformat())
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory', type=Path, default=Path.cwd())
    parser.add_argument('--date', type=date.fromisoformat, help='offline fixture date; live workflow uses UTC today')
    args = parser.parse_args()
    produce(args.output_directory, args.date)

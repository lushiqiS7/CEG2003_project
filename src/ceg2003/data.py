"""Read all supplied XLSX events, audit them, deduplicate and aggregate locally.

The XLSX reader streams public OOXML XML with lxml because the source files
contain millions of cells. PyArrow writes typed batches. DuckDB performs exact
deduplication and aggregation without loading every event into pandas.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, time
from pathlib import Path
import hashlib
import json
import re
import zipfile

import duckdb
from lxml import etree as ET
import openpyxl
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
ALARM_TYPES = [
    'Harsh Braking', 'Harsh Acceleration', 'Sharp Cornering', 'Swaying',
    'Fatigue Alert', 'Yawn', 'Headway Monitoring Alert',
    'Forward Collision Warning', 'Pedestrian Collision Alert', 'Speeding',
]
HARSH = ALARM_TYPES[:4]
FATIGUE = ['Fatigue Alert', 'Yawn']
COLLISION = ['Headway Monitoring Alert', 'Forward Collision Warning', 'Pedestrian Collision Alert']
EXCLUDED_FLAGS = {'duplicate', 'near miss', 'nm'}


def normalise_id(value):
    if value is None or pd.isna(value):
        return None
    value = str(value).strip()
    if value.endswith('.0') and value[:-2].isdigit():
        value = value[:-2]
    return value or None


def parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    text = re.sub(r'\s*\([^)]*\)\s*$', '', str(value).strip())
    for fmt in ('%d-%b-%Y', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def timestamp(value):
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except (TypeError, ValueError):
        return None


def number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')


def _release(element):
    element.clear()
    while element.getprevious() is not None:
        del element.getparent()[0]


def stream_alarm_workbook(source, dest):
    schema = pa.schema([
        ('driver', pa.string()), ('route', pa.string()), ('alarm_type', pa.string()),
        ('speed', pa.float64()), ('start_time', pa.timestamp('us')),
        ('end_time', pa.timestamp('us')), ('duration', pa.float64()),
        ('start_date_serial', pa.float64()), ('source_month', pa.string()),
        ('source_week', pa.string()), ('source_file', pa.string()),
        ('source_sheet', pa.string()), ('source_row', pa.int32()),
    ])
    paths = []
    audits = []
    with zipfile.ZipFile(source) as z:
        strings = []
        with z.open('xl/sharedStrings.xml') as f:
            for _, element in ET.iterparse(f, events=('end',), tag=NS + 'si'):
                strings.append(''.join(element.itertext()))
                _release(element)
        workbook = ET.fromstring(z.read('xl/workbook.xml'))
        rels = {e.get('Id'): e.get('Target') for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sheet in workbook.find(NS + 'sheets'):
            target = rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            out = dest / f'{source.stem}_{sheet.get("name")}.parquet'
            batch = []; n = 0; writer = pq.ParquetWriter(out, schema, compression='zstd')
            try:
                with z.open(target) as f:
                    for _, row in ET.iterparse(f, events=('end',), tag=NS + 'row'):
                        row_no = int(row.get('r'))
                        if row_no == 1:
                            _release(row); continue
                        values = {}
                        for cell in row:
                            col = cell.get('r', '').rstrip('0123456789')
                            v = cell.find(NS + 'v'); value = v.text if v is not None else None
                            if cell.get('t') == 's' and value is not None:
                                value = strings[int(value)]
                            elif cell.get('t') == 'inlineStr':
                                value = ''.join(cell.itertext())
                            values[col] = value
                        if any(values.get(c) is not None for c in 'ABCDEFG'):
                            batch.append({
                                'driver': normalise_id(values.get('A')),
                                'route': normalise_id(values.get('B')),
                                'alarm_type': str(values.get('C') or '').strip(),
                                'speed': number(values.get('D')),
                                'start_time': timestamp(values.get('E')),
                                'end_time': timestamp(values.get('F')),
                                'duration': number(values.get('G')),
                                'start_date_serial': number(values.get('H')),
                                'source_month': values.get('I'), 'source_week': values.get('J'),
                                'source_file': source.name, 'source_sheet': sheet.get('name'),
                                'source_row': row_no,
                            })
                            n += 1
                        _release(row)
                        if len(batch) >= 50000:
                            writer.write_table(pa.Table.from_pylist(batch, schema=schema)); batch.clear()
                if batch:
                    writer.write_table(pa.Table.from_pylist(batch, schema=schema))
            finally:
                writer.close()
            paths.append(out)
            audits.append({'source_file': source.name, 'sheet': sheet.get('name'), 'raw_rows': n})
            print(f'Imported {source.name} / {sheet.get("name")}: {n:,} events', flush=True)
    return paths, audits


def clean_accidents(root):
    source = root / 'data/raw/Traffic Accident Database 2024.xlsx'
    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    records = []
    try:
        for row_no, row in enumerate(wb['Database'].iter_rows(values_only=True), start=1):
            if row_no == 1 or not any(v is not None for v in row[:6]):
                continue
            driver = normalise_id(row[5]); flag = str(row[1] or '').strip().lower()
            day = parse_date(row[3]); clock = row[2]
            if isinstance(clock, datetime): clock = clock.time()
            valid_driver = bool(driver and driver.isdigit())
            reason = ('excluded_incident_flag' if flag in EXCLUDED_FLAGS else
                      'non_single_employee_id' if not valid_driver else
                      'unparsed_date' if day is None else 'eligible_provisional')
            records.append({
                'source_row': row_no, 'report_id': normalise_id(row[0]),
                'driver': driver, 'route': normalise_id(row[4]), 'date': day,
                'time': clock.isoformat() if isinstance(clock, time) else str(clock),
                'flag': flag, 'eligible': reason == 'eligible_provisional',
                'unflagged_sensitivity_eligible': reason == 'eligible_provisional' and flag == '',
                'decision': reason,
                'unresolved_code': flag not in EXCLUDED_FLAGS and flag != '',
            })
    finally:
        wb.close()
    frame = pd.DataFrame(records)
    frame['date'] = pd.to_datetime(frame['date'])
    frame.to_parquet(root / 'data/processed/accidents_audit.parquet', index=False)
    frame.to_csv(root / 'results/accident_cleaning_log.csv', index=False)
    return frame


def prepare_data(root, force=False):
    raw = root / 'data/raw'; dest = root / 'data/processed'
    config = json.loads((root / 'project_config.json').read_text())
    night_hours = config['night_hours']
    if not night_hours or any(not isinstance(h, int) or not 0 <= h <= 23 for h in night_hours):
        raise ValueError('night_hours must contain valid integer hours in 0..23.')
    night_sql = '(' + ','.join(str(h) for h in sorted(set(night_hours))) + ')'
    batch_dir = dest / 'event_cache'; batch_dir.mkdir(parents=True, exist_ok=True)
    for p in ('results', 'results/figures', 'models', 'tmp', 'report', 'presentation', 'notebooks', 'submission'):
        (root / p).mkdir(parents=True, exist_ok=True)
    inputs = ['Mar24_part1.xlsx', 'Mar24_part2.xlsx', 'Traffic Accident Database 2024.xlsx']
    fingerprints = {name: sha256_file(raw / name) for name in inputs}
    manifest_path = dest / 'ingestion_manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    files = [Path(p) for p in manifest.get('parquet_files', [])]
    if force or manifest.get('fingerprints') != fingerprints or not files or not all(p.exists() for p in files):
        files = []; sheets = []
        for name in inputs[:2]:
            paths, audits = stream_alarm_workbook(raw / name, batch_dir)
            files.extend(paths); sheets.extend(audits)
        manifest = {'fingerprints': fingerprints, 'parquet_files': [str(p) for p in files], 'sheets': sheets, 'schema_version': 1}
        write_json(manifest_path, manifest)
    else:
        print('Reusing fingerprint-verified event cache.', flush=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    con.execute("SET threads=4")
    con.execute(f"SET temp_directory='{(root / 'tmp/duckdb').as_posix()}'")
    con.from_parquet([str(p) for p in files]).create_view('raw_events')
    types_sql = ','.join("'" + t + "'" for t in ALARM_TYPES)
    valid = f"start_time >= TIMESTAMP '2024-03-01' AND start_time < TIMESTAMP '2024-04-01' AND end_time >= start_time AND alarm_type IN ({types_sql})"
    raw_stats = con.execute(f"""SELECT COUNT(*) raw_rows, COUNT(*) FILTER(WHERE driver IS NULL) missing_driver,
        COUNT(*) FILTER(WHERE route IS NULL) missing_route,
        COUNT(*) FILTER(WHERE NOT COALESCE(({valid}), FALSE)) invalid_events,
        COUNT(*) FILTER(WHERE duration < 0 OR duration IS NULL) invalid_recorded_duration,
        COUNT(*) FILTER(WHERE ABS(duration - date_diff('second', start_time, end_time)) > 0.001) duration_mismatches,
        COUNT(*) FILTER(WHERE start_date_serial IS NOT NULL AND CAST(DATE '1899-12-30' + CAST(start_date_serial AS INTEGER) AS DATE) <> CAST(start_time AS DATE)) startdate_mismatches,
        MIN(speed) min_speed, MAX(speed) max_speed
        FROM raw_events""").df().iloc[0].to_dict()
    print('Deduplicating exact event keys and validating timestamps...', flush=True)
    con.execute(f"""CREATE TABLE deduplicated AS
        SELECT * EXCLUDE(duplicate_rank) FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY driver, route, alarm_type, speed, start_time, end_time, duration
                ORDER BY source_file, source_sheet, source_row) duplicate_rank
            FROM raw_events
        ) WHERE duplicate_rank = 1""")
    dedup_rows = con.execute('SELECT COUNT(*) FROM deduplicated').fetchone()[0]
    invalid_unique = con.execute(f'SELECT COUNT(*) FROM deduplicated WHERE NOT COALESCE(({valid}), FALSE)').fetchone()[0]
    con.execute(f"CREATE TABLE events AS SELECT *, CAST(start_time AS DATE) event_date, EXTRACT(hour FROM start_time)::INTEGER event_hour FROM deduplicated WHERE {valid}")
    con.execute('DROP TABLE deduplicated')
    cleaned_stats = con.execute('SELECT COUNT(*) clean_rows, COUNT(*) FILTER(WHERE driver IS NULL) unassigned_rows, COUNT(DISTINCT driver) unique_drivers FROM events').df().iloc[0].to_dict()
    mapping = con.execute('SELECT DISTINCT driver FROM events WHERE driver IS NOT NULL ORDER BY driver').df()
    mapping['captain_id'] = [f'CAP-{i:04d}' for i in range(1, len(mapping) + 1)]
    mapping.to_csv(dest / 'driver_id_map_PRIVATE.csv', index=False)
    con.register('driver_mapping', mapping)
    con.execute("CREATE VIEW assigned AS SELECT e.*, m.captain_id FROM events e JOIN driver_mapping m USING(driver)")
    def save_query(query, path):
        out = con.execute(query).df()
        out.to_parquet(dest / path, index=False)
        return out
    save_query("""SELECT event_date AS date, COALESCE(route, 'Unknown') route, alarm_type,
        COUNT(*) events, COUNT(*) FILTER(WHERE driver IS NULL) unassigned_events,
        COUNT(DISTINCT driver) distinct_drivers FROM events GROUP BY ALL""", 'fleet_daily.parquet')
    save_query("""SELECT event_date AS date, event_hour AS hour, COALESCE(route, 'Unknown') route,
        alarm_type, COUNT(*) events FROM events GROUP BY ALL""", 'fleet_hourly.parquet')
    save_query("""SELECT captain_id, event_date AS date, COALESCE(route, 'Unknown') route,
        alarm_type, COUNT(*) events FROM assigned GROUP BY ALL""", 'captain_daily_route_type.parquet')
    def in_sql(values): return '(' + ','.join("'" + v + "'" for v in values) + ')'
    daily = save_query(f"""SELECT captain_id, event_date AS date, COUNT(*) events,
        COUNT(*) FILTER(WHERE alarm_type IN {in_sql(HARSH)}) harsh_events,
        COUNT(*) FILTER(WHERE alarm_type IN {in_sql(FATIGUE)}) fatigue_events,
        COUNT(*) FILTER(WHERE alarm_type IN {in_sql(COLLISION)}) collision_events,
        COUNT(*) FILTER(WHERE alarm_type = 'Speeding') speeding_events,
        COUNT(*) FILTER(WHERE event_hour IN {night_sql}) night_events,
        SUM(speed) event_speed_sum, COUNT(speed) event_speed_count,
        SUM(date_diff('second', start_time, end_time)) elapsed_alarm_seconds
        FROM assigned GROUP BY ALL""", 'captain_daily.parquet')
    categories = con.execute('SELECT alarm_type, COUNT(*) events FROM events GROUP BY 1 ORDER BY 2 DESC').df()
    categories.to_csv(root / 'results/alarm_counts.csv', index=False)
    con.close()
    accidents = clean_accidents(root)
    accidents = accidents.merge(mapping, on='driver', how='left', validate='many_to_one')
    accidents.to_parquet(dest / 'accidents_audit.parquet', index=False)
    accident_months = accidents.assign(month=accidents['date'].dt.strftime('%Y-%m')).groupby('month').agg(raw_reports=('report_id', 'size'), eligible_provisional=('eligible', 'sum')).reset_index()
    accident_months.to_csv(root / 'results/accident_month_counts.csv', index=False)
    audit = {
        'raw': raw_stats, 'clean': cleaned_stats,
        'exact_duplicate_rows_removed': int(raw_stats['raw_rows']) - dedup_rows,
        'invalid_unique_events_removed': invalid_unique,
        'sheet_counts': manifest['sheets'], 'source_sha256': fingerprints,
        'accidents': {'raw_reports': len(accidents), 'eligible_provisional': int(accidents.eligible.sum()),
            'excluded_flags': int(accidents.flag.isin(EXCLUDED_FLAGS).sum()),
            'non_single_employee_rows': int((accidents.decision == 'non_single_employee_id').sum()),
            'unique_report_ids': int(accidents.report_id.nunique()),
            'date_min': str(accidents.date.min().date()), 'date_max': str(accidents.date.max().date()),
            'unresolved_code_rows': int(accidents.unresolved_code.sum()),
            'eligible_unmatched_rows': int((accidents.eligible & accidents.captain_id.isna()).sum())},
        'deduplication_policy': 'Exact event identity across driver, route, type, speed, start, end and recorded duration; retain first provenance. Repeated legitimate identical events cannot be distinguished without event IDs.',
        'incidents_policy': 'Provisional recorded involvement. Exclude explicit duplicate/near-miss flags and invalid identity/date. Other codes remain unresolved, not confirmed at-fault accidents.',
    }
    write_json(root / 'results/quality_audit.json', audit)
    pd.DataFrame([
        {'stage': 'Raw alarm rows', 'rows': int(raw_stats['raw_rows'])},
        {'stage': 'Exact duplicate rows excluded', 'rows': audit['exact_duplicate_rows_removed']},
        {'stage': 'Invalid unique events excluded', 'rows': invalid_unique},
        {'stage': 'Clean fleet events', 'rows': int(cleaned_stats['clean_rows'])},
        {'stage': 'Clean unassigned events', 'rows': int(cleaned_stats['unassigned_rows'])},
        {'stage': 'Clean assigned events', 'rows': int(cleaned_stats['clean_rows'] - cleaned_stats['unassigned_rows'])},
    ]).to_csv(root / 'results/cleaning_reconciliation.csv', index=False)
    return daily, accidents, audit

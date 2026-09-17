"""Seeded behavioral coding fixtures with independent database-state graders.

Calibration runs the same graders against known broken and correct targets.
It validates the graders, not the ability of a model to repair the target.
"""
import importlib.util
from pathlib import Path
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor


BROKEN_SALES = '''import sqlite3

def checkout(db_path, qty, request_key, fail_after_bill=False):
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        conn.execute("INSERT INTO sales(request_key,qty) VALUES(?,?)", (request_key, qty))
        sale_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        if fail_after_bill:
            raise RuntimeError("simulated write failure")
        conn.execute("UPDATE stock SET qty=qty-? WHERE id=1", (qty,))
        conn.commit()
        return sale_id
    finally:
        conn.close()
'''


REFERENCE_SALES = '''import sqlite3

def checkout(db_path, qty, request_key, fail_after_bill=False):
    if not isinstance(qty, int) or qty <= 0:
        raise ValueError("quantity must be positive")
    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT id,qty FROM sales WHERE request_key=?", (request_key,)).fetchone()
        if existing:
            if existing[1] != qty:
                raise ValueError("request key reused with a different quantity")
            conn.commit()
            return existing[0]
        updated = conn.execute("UPDATE stock SET qty=qty-? WHERE id=1 AND qty>=?", (qty, qty))
        if updated.rowcount != 1:
            raise ValueError("insufficient stock")
        conn.execute("INSERT INTO sales(request_key,qty) VALUES(?,?)", (request_key, qty))
        sale_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        if fail_after_bill:
            raise RuntimeError("simulated write failure")
        conn.commit()
        return sale_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
'''


CASES = {
    'E05': 'แก้ checkout ให้บันทึกบิลและตัด stock ใน transaction เดียว หาก fail_after_bill=True ต้อง rollback ทั้งหมด',
    'E06': 'แก้ checkout ให้ request_key เดิมกดซ้ำแล้วได้ sale เดิม ไม่สร้างบิลหรือตัด stock ซ้ำ และ key เดิมกับ qty ต่างกันต้องปฏิเสธ',
    'E08': 'แก้ checkout ให้คำสั่งขายพร้อมกันไม่ทำ stock ติดลบ จำนวนขายรวมต้องตรงกับจำนวน stock ที่หายไป',
}


def prepare_fixture(workspace):
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    (root / 'sales.py').write_text(BROKEN_SALES)
    (root / 'README.md').write_text(
        'Implement checkout(db_path, qty, request_key, fail_after_bill=False) in sales.py. '
        'The host owns schema: stock(id INTEGER PRIMARY KEY, qty INTEGER NOT NULL); '
        'sales(id INTEGER PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, qty INTEGER NOT NULL). '
        'Return sale id; insufficient stock and conflicting idempotency keys raise ValueError. '
        'Use Python standard library; do not add dependencies. Grading uses isolated SQLite databases.\n')
    return str(root / 'sales.py')


def _load_target(path):
    name = 'sales_target_' + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, path)
    target = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(target)
    return target


def _seed(path, quantity=10):
    with sqlite3.connect(path) as conn:
        conn.executescript('CREATE TABLE stock(id INTEGER PRIMARY KEY,qty INTEGER NOT NULL); '
                           'CREATE TABLE sales(id INTEGER PRIMARY KEY,request_key TEXT UNIQUE NOT NULL,qty INTEGER NOT NULL);')
        conn.execute('INSERT INTO stock VALUES(1,?)', (quantity,))


def _state(path):
    with sqlite3.connect(path) as conn:
        return {'stock': conn.execute('SELECT qty FROM stock WHERE id=1').fetchone()[0],
                'sales_count': conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0],
                'sales_qty': conn.execute('SELECT COALESCE(SUM(qty),0) FROM sales').fetchone()[0]}


def grade_sales(case_id, candidate_path, oracle_directory):
    directory = Path(oracle_directory)
    directory.mkdir(parents=True, exist_ok=True)
    observations = []
    try:
        target = _load_target(candidate_path)
        if case_id == 'E05':
            for quantity in (1, 3, 7):
                db = directory / f'atomic-{uuid.uuid4().hex}.db'
                _seed(db)
                try:
                    target.checkout(str(db), quantity, 'fault', fail_after_bill=True)
                    failure_raised = False
                except RuntimeError:
                    failure_raised = True
                actual = _state(db)
                observations.append({'fault_raised': failure_raised, 'actual': actual})
                if not failure_raised or actual != {'stock': 10, 'sales_count': 0, 'sales_qty': 0}:
                    raise AssertionError('Partial billing/stock state survived injected failure')
                target.checkout(str(db), quantity, 'success')
                if _state(db) != {'stock': 10 - quantity, 'sales_count': 1, 'sales_qty': quantity}:
                    raise AssertionError('Successful checkout did not persist both bill and stock')
        elif case_id == 'E06':
            for quantity in (2, 4):
                db = directory / f'idempotent-{uuid.uuid4().hex}.db'
                _seed(db)
                first = target.checkout(str(db), quantity, 'same-key')
                second = target.checkout(str(db), quantity, 'same-key')
                actual = _state(db)
                observations.append({'same_id': first == second, 'actual': actual})
                if first != second or actual != {'stock': 10 - quantity, 'sales_count': 1, 'sales_qty': quantity}:
                    raise AssertionError('Repeated checkout changed sale or stock')
                try:
                    target.checkout(str(db), quantity + 1, 'same-key')
                except ValueError:
                    pass
                else:
                    raise AssertionError('Conflicting idempotency payload accepted')
                if _state(db) != actual:
                    raise AssertionError('Rejected duplicate changed persisted data')
        elif case_id == 'E08':
            for _ in range(3):
                db = directory / f'concurrent-{uuid.uuid4().hex}.db'
                _seed(db, 5)
                def sell(index):
                    try:
                        target.checkout(str(db), 1, f'sale-{index}')
                        return True
                    except ValueError:
                        return False
                with ThreadPoolExecutor(max_workers=8) as executor:
                    successes = list(executor.map(sell, range(12)))
                actual = _state(db)
                observations.append({'successes': sum(successes), 'actual': actual})
                if sum(successes) != 5 or actual != {'stock': 0, 'sales_count': 5, 'sales_qty': 5}:
                    raise AssertionError('Concurrent sales violated stock/accounting invariants')
        else:
            raise ValueError('Unknown behavioral fixture')
        return {'case_id': case_id, 'status': 'PASSED', 'observations': observations,
                'evidence_kind': 'SQLITE_PERSISTED_STATE', 'live_api_verified': False}
    except Exception as error:
        return {'case_id': case_id, 'status': 'FAILED', 'observations': observations,
                'error': f'{type(error).__name__}: {error}', 'evidence_kind': 'SQLITE_PERSISTED_STATE',
                'live_api_verified': False}


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=list(CASES), required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--oracle-dir', required=True)
    args = parser.parse_args()
    result = grade_sales(args.case, args.candidate, args.oracle_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())

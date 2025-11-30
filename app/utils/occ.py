from functools import wraps
from typing import Optional, Tuple, List, Dict
from app.extensions import db


def occ_execute(read_version_sql: str,
			read_params: dict,
			build_update_fn,
			session=None,
			commit: bool = True) -> bool:
	"""Generic OCC executor for arbitrary tables and SQL.

	Parameters:
	- read_version_sql: SQL to read current version by id (must return column 'version').
	- read_params: parameters for the read query.
	- build_update_fn: callable taking expected_version -> (update_sql, update_params).
	  The returned UPDATE must include version condition `(version = :expected_version OR version IS NULL)`
	  and set `version = :new_version`.
	- session: SQLAlchemy session (defaults to db.session).
	- max_retries: number of OCC retry attempts on conflict.

	Returns True if committed successfully, False on not found or conflict exhaustion.
	"""
	if session is None:
		session = db.session

	
	cur = session.execute(db.text(read_version_sql), read_params).mappings().first()
	if not cur:
		return False
	expected_version = int(cur.get('version', 0))

	update_sql, update_params = build_update_fn(expected_version)
	sql = update_sql if hasattr(update_sql, 'text') else db.text(update_sql)

	res = session.execute(sql, update_params)
	if res.rowcount == 1:
		if commit:
			session.commit()
		return True
	if commit:
		session.rollback()

	return False


def occ_batch_update_quantity(ops: List[Dict], session=None) -> bool:
	"""Atomic multi-row optimistic quantity update.

	ops: list of {'id': <item_id>, 'delta': <int>} (delta may be negative or positive)
	For each row we enforce WHERE id=:id AND (version=:expected_version OR version IS NULL)
	and bump version. For negative delta we also ensure quantity >= abs(delta) to avoid underflow.

	Returns True if all updates applied and committed; False on conflict exhaustion or missing rows / underflow.
	"""
	if session is None:
		session = db.session

	item_ids = [op['id'] for op in ops if 'id' in op and isinstance(op.get('delta'), int)]
	if not item_ids:
		return False

		# Read current states for all rows
		placeholders = ','.join(str(int(i)) for i in item_ids)
		select_sql = db.text(f"SELECT id, quantity, COALESCE(version,0) AS version FROM warehouse_items WHERE id IN ({placeholders}) FOR UPDATE")
		current_rows = session.execute(select_sql).mappings().all()
		if len(current_rows) != len(item_ids):
			session.rollback()
			return False  # some rows missing

		current_map = {r['id']: r for r in current_rows}

		# Pre-check underflow
		for op in ops:
			delta = op['delta']
			if delta < 0:
				row = current_map.get(op['id'])
				if row is None or row['quantity'] < -delta:
					session.rollback()
					return False

		all_ok = True
		# Apply each update
		for op in ops:
			row = current_map[op['id']]
			expected_version = int(row['version'])
			update_sql = db.text("""
				UPDATE warehouse_items
				SET quantity = quantity + :delta, version = :new_version
				WHERE id = :id AND (version = :expected_version OR version IS NULL)
			""")
			params = {
				'id': op['id'],
				'delta': op['delta'],
				'expected_version': expected_version,
				'new_version': expected_version + 1,
			}
			res = session.execute(update_sql, params)
			if res.rowcount != 1:
				all_ok = False
				break

		if all_ok:
			session.commit()
			return True
		# conflict: rollback & retry
		session.rollback()


	return False


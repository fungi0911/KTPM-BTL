from functools import wraps
from typing import List, Dict
from app.extensions import db


def occ_execute(read_version_sql: str,
				read_params: dict,
				build_update_fn,
				session=None,
				commit: bool = True,
				expected_version_override: int | None = None) -> bool:
	"""Generic OCC executor.

	If expected_version_override is provided, it is used instead of the current stored version
	(still reads row for existence). UPDATE must guard with version condition and bump version.
	"""
	if session is None:
		session = db.session

	cur = session.execute(db.text(read_version_sql), read_params).mappings().first()
	if not cur:
		return False
	if expected_version_override is not None:
		expected_version = int(expected_version_override)
	else:
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


# def occ_batch_update_quantity(ops: List[Dict], session=None) -> bool:
# 	"""Atomic multi-row optimistic quantity update with simple single attempt.
# 	Returns True if all succeed, False otherwise.
# 	"""
# 	if session is None:
# 		session = db.session

# 	item_ids = [op['id'] for op in ops if 'id' in op and isinstance(op.get('delta'), int)]
# 	if not item_ids:
# 		return False

# 	placeholders = ','.join(str(int(i)) for i in item_ids)
# 	select_sql = db.text(
# 		f"SELECT id, quantity, COALESCE(version,0) AS version FROM warehouse_items WHERE id IN ({placeholders}) FOR UPDATE"
# 	)
# 	current_rows = session.execute(select_sql).mappings().all()
# 	if len(current_rows) != len(item_ids):
# 		session.rollback()
# 		return False

# 	current_map = {r['id']: r for r in current_rows}

# 	for op in ops:
# 		delta = op['delta']
# 		if delta < 0:
# 			row = current_map.get(op['id'])
# 			if row is None or row['quantity'] < -delta:
# 				session.rollback()
# 				return False

# 	all_ok = True
# 	for op in ops:
# 		row = current_map[op['id']]
# 		expected_version = int(row['version'])
# 		update_sql = db.text(
# 			"""
# 			UPDATE warehouse_items
# 			SET quantity = quantity + :delta, version = :new_version
# 			WHERE id = :id AND (version = :expected_version OR version IS NULL)
# 			"""
# 		)
# 		params = {
# 			'id': op['id'],
# 			'delta': op['delta'],
# 			'expected_version': expected_version,
# 			'new_version': expected_version + 1,
# 		}
# 		res = session.execute(update_sql, params)
# 		if res.rowcount != 1:
# 			all_ok = False
# 			break

# 	if all_ok:
# 		session.commit()
# 		return True
# 	session.rollback()
# 	return False


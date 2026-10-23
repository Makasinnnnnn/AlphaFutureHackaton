"""Route regression checks without PostgreSQL or deleting a test database."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

class Field:
    def __init__(self, name): self.name = name
    def __eq__(self, value): return self.name, value
class Query:
    def where(self, *filters): self.filters = filters; return self
class DB:
    def __init__(self):
        self.item = SimpleNamespace(id=10, user_id=2, is_read=False)
        self.commits = 0
        self.deleted = False
    def scalar(self, query):
        return self.item if all(getattr(self.item, name) == value for name, value in query.filters) else None
    def commit(self): self.commits += 1
    def delete(self, item):
        assert item is self.item
        self.deleted = True

def routes():
    source = ast.parse((Path(__file__).parents[1] / 'app/api/routes.py').read_text())
    functions = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in ('read_notification', 'delete_notification')]
    for node in functions: node.decorator_list = []
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *functions], type_ignores=[])
    namespace = {'select': lambda _: Query(), 'Notification': SimpleNamespace(id=Field('id'), user_id=Field('user_id')), 'Response': lambda **kw: SimpleNamespace(**kw), 'not_found': lambda message: LookupError(message)}
    exec(compile(ast.fix_missing_locations(module), '<notification routes>', 'exec'), namespace)
    return namespace

class NotificationAuthorizationTests(unittest.TestCase):
    def test_owner_can_read_and_delete(self):
        handlers = routes(); db = DB(); user = SimpleNamespace(id=2)
        self.assertEqual(handlers['read_notification'](10, user, db).status_code, 204)
        self.assertTrue(db.item.is_read)
        handlers['delete_notification'](10, user, db)
        self.assertTrue(db.deleted)
        self.assertEqual(db.commits, 2)
    def test_other_user_cannot_read_or_delete(self):
        for name in ('read_notification', 'delete_notification'):
            db = DB()
            with self.assertRaises(LookupError): routes()[name](10, SimpleNamespace(id=3), db)
            self.assertFalse(db.deleted)
            self.assertFalse(db.item.is_read)
            self.assertEqual(db.commits, 0)
    def test_missing_notification_is_not_modified(self):
        db = DB()
        with self.assertRaises(LookupError): routes()['delete_notification'](99, SimpleNamespace(id=2), db)
        self.assertEqual(db.commits, 0)

if __name__ == '__main__': unittest.main()

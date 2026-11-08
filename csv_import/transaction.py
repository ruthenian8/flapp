"""Transaction management for CSV imports."""
from sqlalchemy import text
from .sources import TABLES
from .importer import Importer

def import_sources(engine, sources, errors, mode, importer_class=Importer):
    """Return committed/rolled_back. No schema changes, even on an empty database."""
    with engine.connect() as connection:
        if connection.dialect.name == 'mysql':
            # Refuse engines that cannot guarantee rollback. No DDL is issued.
            # ResultProxy exposes keys() but is not subscriptable in SQLAlchemy
            # 1.3; materialize row pairs before passing them to dict().
            engines = dict(connection.execute(text(
                'SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()')).fetchall())
            unsafe = [name for name in TABLES if engines.get(name) != 'InnoDB']
            if unsafe:
                raise ValueError('Missing or nontransactional tables: ' + ', '.join(unsafe))
            connection.execute(text("SET SESSION sql_mode = 'STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"))
            if connection.execute(text('SELECT @@SESSION.autocommit')).scalar() != 0:
                # SQLAlchemy controls transactions; DBAPI autocommit must be disabled.
                connection.execute(text('SET SESSION autocommit = 0'))
        elif connection.dialect.name != 'sqlite':
            raise ValueError('Supported databases: MySQL/InnoDB and SQLite')
        transaction = connection.begin()
        try:
            if connection.dialect.name == 'sqlite':
                # Explicit BEGIN prevents released savepoints from committing the outer unit.
                connection.execute(text('BEGIN'))
            importer = importer_class(connection, sources, errors)
            importer.prepare_people()
            importer.prepare_cards()
            if not errors:
                importer.write()
            if errors or mode == 'dry-run':
                transaction.rollback()
                return 'rolled_back'
            transaction.commit()
            return 'committed'
        except Exception:
            if transaction.is_active:
                transaction.rollback()
            raise



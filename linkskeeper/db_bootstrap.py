from __future__ import annotations

from sqlalchemy import inspect

from flask_migrate import stamp, upgrade

from linkskeeper import create_app, db


def main() -> None:
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        has_app_schema = {"user", "link"}.issubset(tables)
        has_alembic_schema = "alembic_version" in tables

        if has_app_schema and not has_alembic_schema:
            stamp(directory="migrations", revision="head")

        upgrade(directory="migrations")


if __name__ == "__main__":
    main()

import sqlite3
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from main.extensions import db
from main.models.FastQuery import (
    FastQueryProgress,
    FastQuerySection,
    FastQuerySectionCompletion,
)
from main.models.schemas import UserSchemaDatabase


FASTQUERY_LESSONS = (
    {
        "slug": "first-select",
        "title": "1. Your first SELECT",
        "summary": "Read rows and choose the columns you want to see.",
        "sort_order": 1,
        "lesson_data": {
            "intro": "SELECT reads data without changing your database. Start with a table name and choose the fields to display.",
            "steps": [
                {
                    "heading": "Choose fields",
                    "text": "Use a comma-separated list of column names after SELECT.",
                },
                {
                    "heading": "Choose a table",
                    "text": "FROM tells SQLite which table to read. The practice database has users, products, orders, and order_items.",
                },
            ],
            "examples": [
                {
                    "title": "Read a few user details",
                    "description": "This returns three columns for every user.",
                    "query": "SELECT username, email, city\nFROM users;",
                },
                {
                    "title": "Select every column",
                    "description": "The asterisk is a shortcut for all columns. Prefer named columns when you only need some fields.",
                    "query": "SELECT *\nFROM products;",
                },
            ],
            "tip": "The tutorial runs read-only queries. It cannot change or delete rows.",
        },
    },
    {
        "slug": "where-filters",
        "title": "2. Filter with WHERE",
        "summary": "Return only the rows that match a condition.",
        "sort_order": 2,
        "lesson_data": {
            "intro": "WHERE filters rows before SQLite returns the result. Text values go in single quotes; numbers do not need quotes.",
            "steps": [
                {
                    "heading": "Compare values",
                    "text": "Common operators include =, !=, <, <=, >, and >=.",
                },
                {
                    "heading": "Combine conditions",
                    "text": "Use AND when every condition must match, or OR when either condition can match.",
                },
            ],
            "examples": [
                {
                    "title": "Match one city",
                    "description": "Text comparison uses a quoted value.",
                    "query": "SELECT username, city\nFROM users\nWHERE city = 'Seattle';",
                },
                {
                    "title": "Combine conditions",
                    "description": "This finds completed orders with an id greater than 2.",
                    "query": "SELECT id, user_id, status\nFROM orders\nWHERE status = 'Completed' AND id > 2;",
                },
            ],
            "tip": "Use parentheses when combining several AND and OR conditions so the logic is clear.",
        },
    },
    {
        "slug": "sort-and-limit",
        "title": "3. Sort and limit results",
        "summary": "Order rows and keep the result set a useful size.",
        "sort_order": 3,
        "lesson_data": {
            "intro": "ORDER BY sorts a result. Add DESC for descending order or ASC for ascending order. LIMIT caps the number of returned rows.",
            "steps": [
                {
                    "heading": "Sort by a field",
                    "text": "You can sort by one or more columns.",
                },
                {
                    "heading": "Limit the output",
                    "text": "LIMIT is useful for previews and works well with the result viewer's 200-row cap.",
                },
            ],
            "examples": [
                {
                    "title": "Newest users first",
                    "description": "Sort signup dates newest-to-oldest and show only three rows.",
                    "query": "SELECT username, signup_date\nFROM users\nORDER BY signup_date DESC\nLIMIT 3;",
                },
                {
                    "title": "Most expensive products",
                    "description": "Sort numeric prices from highest to lowest.",
                    "query": "SELECT product_name, price\nFROM products\nORDER BY price DESC\nLIMIT 5;",
                },
            ],
            "tip": "When order matters, always specify ORDER BY; database row order is otherwise unspecified.",
        },
    },
    {
        "slug": "search-patterns",
        "title": "4. Search patterns and ranges",
        "summary": "Match text patterns, lists, and numeric ranges.",
        "sort_order": 4,
        "lesson_data": {
            "intro": "LIKE searches text patterns. IN matches any value in a list, and BETWEEN checks an inclusive range.",
            "steps": [
                {
                    "heading": "Use wildcards",
                    "text": "In a LIKE pattern, % matches any number of characters and _ matches one character.",
                },
                {
                    "heading": "Use ranges",
                    "text": "BETWEEN includes both the lower and upper values.",
                },
            ],
            "examples": [
                {
                    "title": "Find products by name",
                    "description": "The percent signs allow any text before or after the word.",
                    "query": "SELECT product_name, category\nFROM products\nWHERE product_name LIKE '%Keyboard%';",
                },
                {
                    "title": "Find products in a price range",
                    "description": "BETWEEN includes prices from 20 through 100.",
                    "query": "SELECT product_name, price\nFROM products\nWHERE price BETWEEN 20 AND 100\nORDER BY price;",
                },
            ],
            "tip": "Use IN ('Pending', 'Completed') instead of repeating the same column comparison with OR.",
        },
    },
    {
        "slug": "null-values",
        "title": "5. Handle missing values",
        "summary": "Check for missing data with IS NULL and IS NOT NULL.",
        "sort_order": 5,
        "lesson_data": {
            "intro": "SQL NULL means a value is missing or unknown. It is not equal to zero or an empty string.",
            "steps": [
                {
                    "heading": "Find missing values",
                    "text": "Use IS NULL to find rows where a field has no value.",
                },
                {
                    "heading": "Find present values",
                    "text": "Use IS NOT NULL to keep rows where a value exists.",
                },
            ],
            "examples": [
                {
                    "title": "Find users without a referrer",
                    "description": "The demo includes users whose referrer is NULL.",
                    "query": "SELECT username, referrer\nFROM users\nWHERE referrer IS NULL;",
                },
                {
                    "title": "Find users with a referrer",
                    "description": "IS NOT NULL is the opposite check.",
                    "query": "SELECT username, referrer\nFROM users\nWHERE referrer IS NOT NULL;",
                },
            ],
            "tip": "Do not write referrer = NULL; use IS NULL or IS NOT NULL.",
        },
    },
    {
        "slug": "aggregate-functions",
        "title": "6. Count and summarize",
        "summary": "Use COUNT, SUM, AVG, MIN, and MAX to summarize rows.",
        "sort_order": 6,
        "lesson_data": {
            "intro": "Aggregate functions turn many rows into summary values. You can give a result a readable name with AS.",
            "steps": [
                {
                    "heading": "Count rows",
                    "text": "COUNT(*) counts rows. COUNT(column) counts rows where that column is not NULL.",
                },
                {
                    "heading": "Calculate values",
                    "text": "SUM adds values, AVG calculates an average, and MIN/MAX find the smallest and largest values.",
                },
            ],
            "examples": [
                {
                    "title": "Count users and orders",
                    "description": "Each count is returned as a single summary row.",
                    "query": "SELECT\n  (SELECT COUNT(*) FROM users) AS user_count,\n  (SELECT COUNT(*) FROM orders) AS order_count;",
                },
                {
                    "title": "Calculate order-item revenue",
                    "description": "Multiply quantity by unit price, then summarize all order items.",
                    "query": "SELECT SUM(quantity * unit_price) AS total_sales,\n       ROUND(AVG(unit_price), 2) AS average_unit_price\nFROM order_items;",
                },
            ],
            "tip": "Aggregate results can be filtered after grouping with HAVING, covered in the next lesson.",
        },
    },
    {
        "slug": "group-results",
        "title": "7. Group results",
        "summary": "Create one summary row per category with GROUP BY and HAVING.",
        "sort_order": 7,
        "lesson_data": {
            "intro": "GROUP BY collects rows with the same value so aggregate functions can summarize each group.",
            "steps": [
                {
                    "heading": "Choose a grouping field",
                    "text": "Every selected field should either be grouped or summarized by an aggregate.",
                },
                {
                    "heading": "Filter groups",
                    "text": "HAVING filters aggregate groups; WHERE filters individual rows before grouping.",
                },
            ],
            "examples": [
                {
                    "title": "Count orders by status",
                    "description": "This returns one row per order status.",
                    "query": "SELECT status, COUNT(*) AS order_count\nFROM orders\nGROUP BY status\nORDER BY order_count DESC;",
                },
                {
                    "title": "Keep categories with multiple products",
                    "description": "HAVING filters the grouped product counts.",
                    "query": "SELECT category, COUNT(*) AS product_count\nFROM products\nGROUP BY category\nHAVING COUNT(*) > 1;",
                },
            ],
            "tip": "Use WHERE for row conditions and HAVING for conditions on grouped totals.",
        },
    },
    {
        "slug": "join-tables",
        "title": "8. Join related tables",
        "summary": "Combine rows from users, orders, products, and order items.",
        "sort_order": 8,
        "lesson_data": {
            "intro": "JOIN combines related tables. Match a primary-key field to its corresponding foreign-key field in the ON clause.",
            "steps": [
                {
                    "heading": "Start with two tables",
                    "text": "orders.user_id points to users.id in the demo database.",
                },
                {
                    "heading": "Add more joins",
                    "text": "You can continue joining tables to follow a relationship chain.",
                },
            ],
            "examples": [
                {
                    "title": "Show each user's orders",
                    "description": "Join users to orders using their id fields.",
                    "query": "SELECT users.username, orders.order_date, orders.status\nFROM users\nJOIN orders ON orders.user_id = users.id\nORDER BY orders.order_date;",
                },
                {
                    "title": "Show products in orders",
                    "description": "Follow orders through order_items to products.",
                    "query": "SELECT users.username, products.product_name,\n       order_items.quantity,\n       order_items.quantity * order_items.unit_price AS line_total\nFROM users\nJOIN orders ON orders.user_id = users.id\nJOIN order_items ON order_items.order_id = orders.id\nJOIN products ON products.id = order_items.product_id\nORDER BY users.username, products.product_name;",
                },
            ],
            "tip": "Use table names before column names, such as users.username, when a join includes similar column names.",
        },
    },
    {
        "slug": "subqueries",
        "title": "9. Use a subquery",
        "summary": "Use one SELECT inside another to answer a multi-step question.",
        "sort_order": 9,
        "lesson_data": {
            "intro": "A subquery is a query nested inside another query. It can provide a list, a single value, or a temporary result.",
            "steps": [
                {
                    "heading": "Build the inner query",
                    "text": "The inner query finds user ids for orders with a selected status.",
                },
                {
                    "heading": "Use the result outside",
                    "text": "The outer query finds the matching usernames.",
                },
            ],
            "examples": [
                {
                    "title": "Find users with pending orders",
                    "description": "The inner SELECT is evaluated as part of the outer query.",
                    "query": "SELECT username\nFROM users\nWHERE id IN (\n  SELECT user_id\n  FROM orders\n  WHERE status = 'Pending'\n)\nORDER BY username;",
                },
            ],
            "tip": "If a nested query becomes hard to read, a JOIN may express the same relationship more clearly.",
        },
    },
    {
        "slug": "case-expressions",
        "title": "10. Label values with CASE",
        "summary": "Create readable categories from values in a query result.",
        "sort_order": 10,
        "lesson_data": {
            "intro": "CASE evaluates conditions in order and returns the result for the first matching branch.",
            "steps": [
                {
                    "heading": "Add conditions",
                    "text": "Each WHEN condition has a THEN result. ELSE handles values that did not match.",
                },
                {
                    "heading": "Name the output",
                    "text": "Use AS to give the calculated column a useful heading.",
                },
            ],
            "examples": [
                {
                    "title": "Classify product prices",
                    "description": "Each product gets a budget, standard, or premium label.",
                    "query": "SELECT product_name, price,\n       CASE\n         WHEN price >= 100 THEN 'Premium'\n         WHEN price >= 20 THEN 'Standard'\n         ELSE 'Budget'\n       END AS price_band\nFROM products\nORDER BY price DESC;",
                },
            ],
            "tip": "Place the most specific or highest threshold conditions first.",
        },
    },
    {
        "slug": "inspect-schema",
        "title": "11. Inspect the database",
        "summary": "List tables and inspect their stored CREATE TABLE statements.",
        "sort_order": 11,
        "lesson_data": {
            "intro": "SQLite keeps table definitions in sqlite_master. Query it to learn which tables exist and how they were created.",
            "steps": [
                {
                    "heading": "List application tables",
                    "text": "The sqlite_% filter hides SQLite's internal tables.",
                },
                {
                    "heading": "Inspect a definition",
                    "text": "The sql column contains a table's CREATE TABLE statement.",
                },
            ],
            "examples": [
                {
                    "title": "List tables",
                    "description": "This query is also available as the default in the Schema query editor.",
                    "query": "SELECT name\nFROM sqlite_master\nWHERE type = 'table' AND name NOT LIKE 'sqlite_%'\nORDER BY name;",
                },
                {
                    "title": "Inspect the users table",
                    "description": "Change the table name inside the final condition to inspect another table.",
                    "query": "SELECT name, sql\nFROM sqlite_master\nWHERE type = 'table' AND name = 'users';",
                },
            ],
            "tip": "The tutorial query runner is read-only, so SQLite PRAGMA statements are intentionally unavailable.",
        },
    },
)


def _create_demo_database():
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                city TEXT NOT NULL,
                signup_date TEXT NOT NULL,
                referrer TEXT
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL
            );
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                order_date TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                product_id INTEGER NOT NULL REFERENCES products(id),
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL
            );
            INSERT INTO users (username, email, city, signup_date, referrer) VALUES
                ('Avery', 'avery@example.test', 'Seattle', '2025-01-15', NULL),
                ('Blake', 'blake@example.test', 'Portland', '2025-02-02', 'Avery'),
                ('Casey', 'casey@example.test', 'Seattle', '2025-03-19', NULL),
                ('Drew', 'drew@example.test', 'Austin', '2025-04-04', 'Blake'),
                ('Emery', 'emery@example.test', 'Portland', '2025-05-21', NULL);
            INSERT INTO products (product_name, category, price) VALUES
                ('Keyboard', 'Accessories', 79.00),
                ('Mouse', 'Accessories', 35.50),
                ('Monitor', 'Displays', 229.99),
                ('Desk Lamp', 'Office', 24.00),
                ('Notebook', 'Office', 8.50);
            INSERT INTO orders (user_id, order_date, status) VALUES
                (1, '2025-06-01', 'Completed'),
                (2, '2025-06-03', 'Pending'),
                (1, '2025-06-08', 'Completed'),
                (3, '2025-06-11', 'Cancelled'),
                (4, '2025-06-13', 'Completed'),
                (5, '2025-06-18', 'Pending'),
                (2, '2025-06-21', 'Completed');
            INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
                (1, 1, 1, 79.00),
                (1, 2, 1, 35.50),
                (2, 3, 1, 229.99),
                (3, 4, 2, 24.00),
                (3, 5, 3, 8.50),
                (4, 2, 1, 35.50),
                (5, 3, 2, 219.99),
                (5, 4, 1, 24.00),
                (6, 5, 5, 8.50),
                (7, 1, 1, 79.00);
            """
        )
        connection.commit()
        return connection.serialize(), _schema_data_from_connection(connection)
    finally:
        connection.close()


def _schema_data_from_connection(connection):
    table_rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    table_ids = {name: str(index + 1) for index, (name,) in enumerate(table_rows)}
    column_ids = {}
    tables = []
    next_column_id = 1

    for index, (table_name,) in enumerate(table_rows):
        columns = []
        column_ids[table_name] = {}
        for _, name, declared_type, _, _, primary_key in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall():
            column_type = (declared_type or "").upper()
            if primary_key and column_type == "INTEGER":
                data_type = "AutoNumber"
            elif column_type == "INTEGER":
                data_type = "Number"
            elif column_type in {"REAL", "FLOAT", "DOUBLE"}:
                data_type = "Decimal"
            elif column_type == "NUMERIC":
                data_type = "Currency"
            else:
                data_type = "Short Text"
            column_id = str(next_column_id)
            next_column_id += 1
            column_ids[table_name][name] = column_id
            columns.append(
                {
                    "id": column_id,
                    "name": name,
                    "type": data_type,
                    "primaryKey": bool(primary_key),
                }
            )
        tables.append(
            {
                "id": table_ids[table_name],
                "name": table_name,
                "x": 24 + index % 2 * 320,
                "y": 24 + index // 2 * 240,
                "columns": columns,
            }
        )

    relationships = []
    next_relationship_id = 1
    for table_name, in table_rows:
        foreign_keys = connection.execute(
            f'PRAGMA foreign_key_list("{table_name}")'
        ).fetchall()
        for foreign_key in foreign_keys:
            _, _, target_table, source_column, target_column, *_ = foreign_key
            relationships.append(
                {
                    "id": str(next_relationship_id),
                    "sourceTableId": table_ids[table_name],
                    "targetTableId": table_ids[target_table],
                    "sourceColumnId": column_ids[table_name][source_column],
                    "targetColumnId": column_ids[target_table][target_column],
                    "color": "#2878b5",
                }
            )
            next_relationship_id += 1
    return {"tables": tables, "relationships": relationships}


def _section_data(section):
    return {
        "id": section.section_id,
        "slug": section.slug,
        "title": section.title,
        "summary": section.summary,
        "sortOrder": section.sort_order,
        "lesson": section.lesson_data,
        "createdAt": section.created_at.isoformat(),
        "updatedAt": section.updated_at.isoformat(),
    }


def _build_state(progress, sections):
    completions = FastQuerySectionCompletion.query.filter_by(
        progress_id=progress.progress_id
    ).all()
    completed_section_ids = {completion.section_id for completion in completions}
    return {
        "sections": [_section_data(section) for section in sections],
        "progress": {
            "currentSection": progress.current_section.slug,
            "completedSections": [
                section.slug
                for section in sections
                if section.section_id in completed_section_ids
            ],
            "startedAt": progress.started_at.isoformat(),
            "lastAccessedAt": progress.last_accessed_at.isoformat(),
        },
        "demoDatabase": {
            "id": progress.demo_database.schema_database_id,
            "name": progress.demo_database.schema_name,
            "fileName": progress.demo_database.file_name,
        },
    }


def ensure_fastquery_state(user_id, retry=False):
    now = datetime.now(timezone.utc)
    sections = []
    for lesson in FASTQUERY_LESSONS:
        section = FastQuerySection.query.filter_by(slug=lesson["slug"]).first()
        if section is None:
            section = FastQuerySection(**lesson)
            db.session.add(section)
        else:
            changed = False
            for key in ("title", "summary", "sort_order", "lesson_data"):
                if getattr(section, key) != lesson[key]:
                    setattr(section, key, lesson[key])
                    changed = True
            if changed:
                section.updated_at = now
        sections.append(section)

    db.session.flush()
    sections.sort(key=lambda section: section.sort_order)

    progress = FastQueryProgress.query.filter_by(user_id=user_id).first()
    if progress is None:
        progress = FastQueryProgress(user_id=user_id)
        db.session.add(progress)
        db.session.flush()
    if progress.current_section_id is None:
        progress.current_section_id = sections[0].section_id
    progress.last_accessed_at = now

    demo_database = None
    if progress.demo_database_id is not None:
        demo_database = UserSchemaDatabase.query.filter_by(
            schema_database_id=progress.demo_database_id,
            user_id=user_id,
            is_fastquery_demo=True,
        ).first()
    if demo_database is None:
        progress.demo_database_id = None
        demo_database = UserSchemaDatabase.query.filter_by(
            user_id=user_id,
            is_fastquery_demo=True,
        ).first()

    if demo_database is None:
        database_data, schema_data = _create_demo_database()
        name = "user.db"
        if UserSchemaDatabase.query.filter_by(
            user_id=user_id, schema_name=name
        ).first():
            name = "user.db (FastQuery)"
        demo_database = UserSchemaDatabase(
            user_id=user_id,
            schema_name=name,
            file_name="user.db",
            database_data=database_data,
            schema_data=schema_data,
            is_fastquery_demo=True,
        )
        db.session.add(demo_database)
        db.session.flush()
    progress.demo_database_id = demo_database.schema_database_id

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if retry:
            raise
        return ensure_fastquery_state(user_id, retry=True)

    progress = FastQueryProgress.query.filter_by(user_id=user_id).one()
    sections = FastQuerySection.query.order_by(FastQuerySection.sort_order).all()
    return _build_state(progress, sections)


def save_fastquery_progress(user_id, slug, complete=False):
    ensure_fastquery_state(user_id)
    section = FastQuerySection.query.filter_by(slug=slug).first()
    if section is None:
        raise ValueError("That tutorial section does not exist.")

    progress = FastQueryProgress.query.filter_by(user_id=user_id).one()
    now = datetime.now(timezone.utc)
    progress.current_section_id = section.section_id
    progress.last_accessed_at = now

    if complete:
        completion = FastQuerySectionCompletion.query.filter_by(
            progress_id=progress.progress_id,
            section_id=section.section_id,
        ).first()
        if completion is None:
            db.session.add(
                FastQuerySectionCompletion(
                    progress_id=progress.progress_id,
                    section_id=section.section_id,
                    completed_at=now,
                )
            )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if complete:
            progress = FastQueryProgress.query.filter_by(user_id=user_id).one()
            progress.current_section_id = section.section_id
            progress.last_accessed_at = now
            completion = FastQuerySectionCompletion.query.filter_by(
                progress_id=progress.progress_id,
                section_id=section.section_id,
            ).first()
            if completion is not None:
                db.session.commit()
                return ensure_fastquery_state(user_id)
        raise

    return ensure_fastquery_state(user_id)

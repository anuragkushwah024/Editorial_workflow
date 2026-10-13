"""
Make the article timeline append-only at the database level (goal 9).

Model-level save()/delete() guards are easy to bypass (QuerySet.update(),
bulk deletes, raw SQL, the admin). This trigger rejects any UPDATE, DELETE or
TRUNCATE on the events table no matter where it comes from, so not even an
editor with database access through the app can rewrite history.
"""

from django.db import migrations

CREATE_SQL = """
CREATE OR REPLACE FUNCTION articles_event_is_immutable()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'article timeline events are append-only (% is not allowed)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER articles_event_no_update_delete
BEFORE UPDATE OR DELETE ON articles_articleevent
FOR EACH ROW EXECUTE FUNCTION articles_event_is_immutable();

CREATE TRIGGER articles_event_no_truncate
BEFORE TRUNCATE ON articles_articleevent
FOR EACH STATEMENT EXECUTE FUNCTION articles_event_is_immutable();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS articles_event_no_truncate ON articles_articleevent;
DROP TRIGGER IF EXISTS articles_event_no_update_delete ON articles_articleevent;
DROP FUNCTION IF EXISTS articles_event_is_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_SQL, reverse_sql=DROP_SQL),
    ]

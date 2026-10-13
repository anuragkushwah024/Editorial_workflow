# Schema

## Tables and columns

The ER diagram below shows every table with its columns and types.

## One-to-many and many-to-many relationships

_To be written._

## Database rules versus application rules

_To be written._

## What I denormalised

_To be written._

## What would break first at 100x the data

_To be written._

## Database ER diagram

All seven tables live in PostgreSQL. Names are the real table names Django creates. `PK` = primary key, `FK` = foreign key, `UK` = unique.

```mermaid
erDiagram
    accounts_user ||--o{ sections_section : "owns (owner_id)"
    accounts_user ||--o{ sections_sectionassignment : "is assigned (writer_id)"
    accounts_user ||--o{ sections_sectionassignment : "assigns (assigned_by_id)"
    sections_section ||--o{ sections_sectionassignment : "has writers"
    sections_section ||--o{ articles_article : "contains"
    accounts_user ||--o{ articles_article : "writes (author_id)"
    articles_article ||--o{ articles_articlerevision : "has revisions"
    accounts_user ||--o{ articles_articlerevision : "opens (created_by_id)"
    articles_article ||--o{ articles_articleevent : "timeline"
    articles_articlerevision |o--o{ articles_articleevent : "about (optional)"
    accounts_user ||--o{ articles_articleevent : "acts (actor_id)"
    articles_article ||--o{ articles_alertdismissal : "alert dismissed"
    articles_articlerevision |o--o{ articles_alertdismissal : "for revision (optional)"
    accounts_user ||--o{ articles_alertdismissal : "dismisses (dismissed_by_id)"

    accounts_user {
        bigint id PK
        varchar email UK "login, stored lower-case"
        varchar full_name
        varchar role "EDITOR or WRITER"
        varchar password "PBKDF2 hash"
        boolean is_active
        timestamptz date_joined
    }

    sections_section {
        bigint id PK
        varchar name UK
        text description
        bigint owner_id FK "an editor"
        boolean is_archived
        timestamptz archived_at "null unless archived"
        timestamptz created_at
        timestamptz updated_at
    }

    sections_sectionassignment {
        bigint id PK
        bigint section_id FK
        bigint writer_id FK
        bigint assigned_by_id FK
        timestamptz created_at
    }

    articles_article {
        bigint id PK
        bigint section_id FK
        bigint author_id FK
        varchar title "live content"
        text body "live content"
        varchar status "DRAFT to PUBLISHED"
        timestamptz scheduled_for "required when SCHEDULED"
        timestamptz published_at "required when PUBLISHED"
        timestamptz created_at
        timestamptz updated_at
    }

    articles_articlerevision {
        bigint id PK
        bigint article_id FK
        integer number "1, 2, 3 per article"
        bigint created_by_id FK
        varchar title
        text body
        varchar status "own lifecycle"
        timestamptz scheduled_for
        timestamptz published_at
        timestamptz created_at
        timestamptz updated_at
    }

    articles_articleevent {
        bigint id PK
        bigint article_id FK
        bigint revision_id FK "nullable"
        varchar event_type "CREATED, EDITED, STATUS_CHANGED, REVISION_OPENED, REVISION_PUBLISHED, COMMENT"
        varchar from_status
        varchar to_status
        bigint actor_id FK
        text message "comment text or note"
        jsonb payload "e.g. published title and body"
        timestamptz created_at
    }

    articles_alertdismissal {
        bigint id PK
        bigint article_id FK
        bigint revision_id FK "nullable"
        timestamptz scheduled_for "the schedule being dismissed"
        bigint dismissed_by_id FK
        timestamptz dismissed_at
    }
```

`accounts_user` also has Django's standard auth columns (`last_login`, `is_staff`, `is_superuser`, `first_name`, `last_name`), left out of the diagram for clarity.

**Rules enforced by the database itself**

| Table | Rule |
|---|---|
| `accounts_user` | `email` is unique |
| `sections_section` | `name` is unique |
| `sections_sectionassignment` | `(section_id, writer_id)` is unique, so a writer is assigned to a section only once |
| `articles_article` | CHECK: a SCHEDULED article has `scheduled_for`; a PUBLISHED article has `published_at` |
| `articles_articlerevision` | `(article_id, number)` is unique; at most one revision per article that is not PUBLISHED (partial unique index); CHECK: a SCHEDULED revision has `scheduled_for` |
| `articles_articleevent` | Trigger rejects every UPDATE, DELETE and TRUNCATE, so the timeline is insert-only |
| `articles_alertdismissal` | `(article_id, revision_id, scheduled_for)` is unique, with NULL revisions treated as equal |
| All foreign keys | Postgres refuses to delete a row that other rows still point to, so an article with timeline events can never be deleted. Django adds `on_delete=PROTECT` on top for a clear error message; only assignments and alert dismissals are removed along with their parent. |

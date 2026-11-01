-- Executed once by the PostgreSQL image when initializing an empty production volume.
-- psql literal quoting and format(%I/%L) keep identifiers/passwords out of SQL syntax.
\set ON_ERROR_STOP on
\getenv app_user DATABASE_USER
\getenv app_password DATABASE_PASSWORD
\getenv migration_user MIGRATION_DATABASE_USER
\getenv migration_password MIGRATION_DATABASE_PASSWORD
\getenv database_name POSTGRES_DB

SELECT (
    length(:'app_user') > 0
    AND length(:'migration_user') > 0
    AND length(:'app_password') >= 32
    AND length(:'migration_password') >= 32
    AND :'app_user' <> :'migration_user'
    AND :'app_user' <> current_user
    AND :'migration_user' <> current_user
) AS roles_valid \gset
\if :roles_valid
\else
    \echo 'Distinct application/migration roles and strong passwords are required.'
    \quit 1
\endif

SELECT format(
    'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'app_user', :'app_password'
) \gexec
SELECT format(
    'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
    :'migration_user', :'migration_password'
) \gexec

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'database_name') \gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
SELECT format('GRANT CONNECT ON DATABASE %I TO %I, %I', :'database_name', :'app_user', :'migration_user') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'app_user') \gexec
SELECT format('GRANT USAGE, CREATE ON SCHEMA public TO %I', :'migration_user') \gexec
SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
    :'migration_user', :'app_user'
) \gexec
SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO %I',
    :'migration_user', :'app_user'
) \gexec

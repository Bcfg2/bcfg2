BEGIN TRANSACTION;
CREATE TABLE "auth_message" (
    "id" serial PRIMARY KEY,
    "user_id" integer NOT NULL,
    "message" text NOT NULL
);
CREATE TABLE "auth_group" (
    "id" serial PRIMARY KEY,
    "name" varchar(80) NOT NULL UNIQUE
);
CREATE TABLE "auth_user" (
    "id" serial PRIMARY KEY,
    "username" varchar(30) NOT NULL UNIQUE,
    "first_name" varchar(30) NOT NULL,
    "last_name" varchar(30) NOT NULL,
    "email" varchar(75) NOT NULL,
    "password" varchar(128) NOT NULL,
    "is_staff" bool NOT NULL,
    "is_active" bool NOT NULL,
    "is_superuser" bool NOT NULL,
    "last_login" timestamp NOT NULL,
    "date_joined" timestamp NOT NULL
);
INSERT INTO "auth_user" VALUES(1, 'djbclark', '', '', 'danny@laptop.org', 'sha1$a1043$f0904cb26ef42eb5259cf3dcb80dc6c01506ed8c', True, True, True, '2006-06-21 16:42:01.995814', '2006-06-19 15:10:18.850029');
CREATE TABLE "auth_permission" (
    "id" serial PRIMARY KEY,
    "name" varchar(50) NOT NULL,
    "content_type_id" integer NOT NULL,
    "codename" varchar(100) NOT NULL,
    UNIQUE ("content_type_id", "codename")
);
INSERT INTO "auth_permission" VALUES(1, 'Can add message', 1, 'add_message');
INSERT INTO "auth_permission" VALUES(2, 'Can change message', 1, 'change_message');
INSERT INTO "auth_permission" VALUES(3, 'Can delete message', 1, 'delete_message');
INSERT INTO "auth_permission" VALUES(4, 'Can add group', 2, 'add_group');
INSERT INTO "auth_permission" VALUES(5, 'Can change group', 2, 'change_group');
INSERT INTO "auth_permission" VALUES(6, 'Can delete group', 2, 'delete_group');
INSERT INTO "auth_permission" VALUES(7, 'Can add user', 3, 'add_user');
INSERT INTO "auth_permission" VALUES(8, 'Can change user', 3, 'change_user');
INSERT INTO "auth_permission" VALUES(9, 'Can delete user', 3, 'delete_user');
INSERT INTO "auth_permission" VALUES(10, 'Can add permission', 4, 'add_permission');
INSERT INTO "auth_permission" VALUES(11, 'Can change permission', 4, 'change_permission');
INSERT INTO "auth_permission" VALUES(12, 'Can delete permission', 4, 'delete_permission');
INSERT INTO "auth_permission" VALUES(13, 'Can add content type', 5, 'add_contenttype');
INSERT INTO "auth_permission" VALUES(14, 'Can change content type', 5, 'change_contenttype');
INSERT INTO "auth_permission" VALUES(15, 'Can delete content type', 5, 'delete_contenttype');
INSERT INTO "auth_permission" VALUES(16, 'Can add session', 6, 'add_session');
INSERT INTO "auth_permission" VALUES(17, 'Can change session', 6, 'change_session');
INSERT INTO "auth_permission" VALUES(18, 'Can delete session', 6, 'delete_session');
INSERT INTO "auth_permission" VALUES(19, 'Can add site', 7, 'add_site');
INSERT INTO "auth_permission" VALUES(20, 'Can change site', 7, 'change_site');
INSERT INTO "auth_permission" VALUES(21, 'Can delete site', 7, 'delete_site');
INSERT INTO "auth_permission" VALUES(22, 'Can add log entry', 8, 'add_logentry');
INSERT INTO "auth_permission" VALUES(23, 'Can change log entry', 8, 'change_logentry');
INSERT INTO "auth_permission" VALUES(24, 'Can delete log entry', 8, 'delete_logentry');
INSERT INTO "auth_permission" VALUES(25, 'Can add interaction', 9, 'add_interaction');
INSERT INTO "auth_permission" VALUES(26, 'Can change interaction', 9, 'change_interaction');
INSERT INTO "auth_permission" VALUES(27, 'Can delete interaction', 9, 'delete_interaction');
INSERT INTO "auth_permission" VALUES(28, 'Can add repository', 10, 'add_repository');
INSERT INTO "auth_permission" VALUES(29, 'Can change repository', 10, 'change_repository');
INSERT INTO "auth_permission" VALUES(30, 'Can delete repository', 10, 'delete_repository');
INSERT INTO "auth_permission" VALUES(31, 'Can add extra', 11, 'add_extra');
INSERT INTO "auth_permission" VALUES(32, 'Can change extra', 11, 'change_extra');
INSERT INTO "auth_permission" VALUES(33, 'Can delete extra', 11, 'delete_extra');
INSERT INTO "auth_permission" VALUES(34, 'Can add modified', 12, 'add_modified');
INSERT INTO "auth_permission" VALUES(35, 'Can change modified', 12, 'change_modified');
INSERT INTO "auth_permission" VALUES(36, 'Can delete modified', 12, 'delete_modified');
INSERT INTO "auth_permission" VALUES(37, 'Can add bad', 13, 'add_bad');
INSERT INTO "auth_permission" VALUES(38, 'Can change bad', 13, 'change_bad');
INSERT INTO "auth_permission" VALUES(39, 'Can delete bad', 13, 'delete_bad');
INSERT INTO "auth_permission" VALUES(40, 'Can add client', 14, 'add_client');
INSERT INTO "auth_permission" VALUES(41, 'Can change client', 14, 'change_client');
INSERT INTO "auth_permission" VALUES(42, 'Can delete client', 14, 'delete_client');
INSERT INTO "auth_permission" VALUES(43, 'Can add performance', 15, 'add_performance');
INSERT INTO "auth_permission" VALUES(44, 'Can change performance', 15, 'change_performance');
INSERT INTO "auth_permission" VALUES(45, 'Can delete performance', 15, 'delete_performance');
INSERT INTO "auth_permission" VALUES(46, 'Can add metadata', 16, 'add_metadata');
INSERT INTO "auth_permission" VALUES(47, 'Can change metadata', 16, 'change_metadata');
INSERT INTO "auth_permission" VALUES(48, 'Can delete metadata', 16, 'delete_metadata');
INSERT INTO "auth_permission" VALUES(49, 'Can add reason', 17, 'add_reason');
INSERT INTO "auth_permission" VALUES(50, 'Can change reason', 17, 'change_reason');
INSERT INTO "auth_permission" VALUES(51, 'Can delete reason', 17, 'delete_reason');
INSERT INTO "auth_permission" VALUES(52, 'Can add ping', 18, 'add_ping');
INSERT INTO "auth_permission" VALUES(53, 'Can change ping', 18, 'change_ping');
INSERT INTO "auth_permission" VALUES(54, 'Can delete ping', 18, 'delete_ping');
CREATE TABLE "auth_group_permissions" (
    "id" serial PRIMARY KEY,
    "group_id" integer NOT NULL REFERENCES "auth_group" ("id"),
    "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id"),
    UNIQUE ("group_id", "permission_id")
);
CREATE TABLE "auth_user_groups" (
    "id" serial PRIMARY KEY,
    "user_id" integer NOT NULL REFERENCES "auth_user" ("id"),
    "group_id" integer NOT NULL REFERENCES "auth_group" ("id"),
    UNIQUE ("user_id", "group_id")
);
CREATE TABLE "auth_user_user_permissions" (
    "id" serial PRIMARY KEY,
    "user_id" integer NOT NULL REFERENCES "auth_user" ("id"),
    "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id"),
    UNIQUE ("user_id", "permission_id")
);
CREATE TABLE "django_content_type" (
    "id" serial PRIMARY KEY,
    "name" varchar(100) NOT NULL,
    "app_label" varchar(100) NOT NULL,
    "model" varchar(100) NOT NULL,
    UNIQUE ("app_label", "model")
);
INSERT INTO "django_content_type" VALUES(1, 'message', 'auth', 'message');
INSERT INTO "django_content_type" VALUES(2, 'group', 'auth', 'group');
INSERT INTO "django_content_type" VALUES(3, 'user', 'auth', 'user');
INSERT INTO "django_content_type" VALUES(4, 'permission', 'auth', 'permission');
INSERT INTO "django_content_type" VALUES(5, 'content type', 'contenttypes', 'contenttype');
INSERT INTO "django_content_type" VALUES(6, 'session', 'sessions', 'session');
INSERT INTO "django_content_type" VALUES(7, 'site', 'sites', 'site');
INSERT INTO "django_content_type" VALUES(8, 'log entry', 'admin', 'logentry');
INSERT INTO "django_content_type" VALUES(9, 'interaction', 'reports', 'interaction');
INSERT INTO "django_content_type" VALUES(10, 'repository', 'reports', 'repository');
INSERT INTO "django_content_type" VALUES(11, 'extra', 'reports', 'extra');
INSERT INTO "django_content_type" VALUES(12, 'modified', 'reports', 'modified');
INSERT INTO "django_content_type" VALUES(13, 'bad', 'reports', 'bad');
INSERT INTO "django_content_type" VALUES(14, 'client', 'reports', 'client');
INSERT INTO "django_content_type" VALUES(15, 'performance', 'reports', 'performance');
INSERT INTO "django_content_type" VALUES(16, 'metadata', 'reports', 'metadata');
INSERT INTO "django_content_type" VALUES(17, 'reason', 'reports', 'reason');
INSERT INTO "django_content_type" VALUES(18, 'ping', 'reports', 'ping');
CREATE TABLE "django_session" (
    "session_key" varchar(40) NOT NULL PRIMARY KEY,
    "session_data" text NOT NULL,
    "expire_date" timestamp NOT NULL
);
INSERT INTO "django_session" VALUES('f081f2e5fbec289a16c5f9ec883d0cf9', 'KGRwMQpTJ19hdXRoX3VzZXJfaWQnCnAyCkkxCnMuMmI3ZmJiMWY5OTAwZmM0ZWYxOWE0YTNkYzI4
ZTFjNmU=
', '2006-07-05 16:42:02.305576');
CREATE TABLE "django_site" (
    "id" serial PRIMARY KEY,
    "domain" varchar(100) NOT NULL,
    "name" varchar(50) NOT NULL
);
INSERT INTO "django_site" VALUES(1, 'laptop.org', 'laptop.org');
CREATE TABLE "django_admin_log" (
    "id" serial PRIMARY KEY,
    "action_time" timestamp NOT NULL,
    "user_id" integer NOT NULL REFERENCES "auth_user" ("id"),
    "content_type_id" integer NULL REFERENCES "django_content_type" ("id"),
    "object_id" text NULL,
    "object_repr" varchar(200) NOT NULL,
    "action_flag" integer NOT NULL,
    "change_message" text NOT NULL
);
CREATE TABLE "reports_bad" (
    "id" serial PRIMARY KEY,
    "name" varchar(128) NOT NULL,
    "kind" varchar(16) NOT NULL,
    "critical" bool NOT NULL,
    "reason_id" integer NOT NULL
);
CREATE TABLE "reports_repository" (
    "id" serial PRIMARY KEY,
    "timestamp" timestamp NOT NULL
);
CREATE TABLE "reports_extra" (
    "id" serial PRIMARY KEY,
    "name" varchar(128) NOT NULL,
    "kind" varchar(16) NOT NULL,
    "critical" bool NOT NULL,
    "reason_id" integer NOT NULL
);
CREATE TABLE "reports_modified" (
    "id" serial PRIMARY KEY,
    "name" varchar(128) NOT NULL,
    "kind" varchar(16) NOT NULL,
    "critical" bool NOT NULL,
    "reason_id" integer NOT NULL
);
CREATE TABLE "reports_reason" (
    "id" serial PRIMARY KEY,
    "owner" text NOT NULL,
    "current_owner" text NOT NULL,
    "group" text NOT NULL,
    "current_group" text NOT NULL,
    "perms" text NOT NULL,
    "current_perms" text NOT NULL,
    "status" text NOT NULL,
    "current_status" text NOT NULL,
    "to" text NOT NULL,
    "current_to" text NOT NULL,
    "version" text NOT NULL,
    "current_version" text NOT NULL,
    "current_exists" bool NOT NULL,
    "current_diff" text NOT NULL
);
CREATE TABLE "reports_performance" (
    "id" serial PRIMARY KEY,
    "metric" varchar(128) NOT NULL,
    "value" numeric(32, 16) NOT NULL
);
CREATE TABLE reports_interaction (id serial PRIMARY KEY, client_id integer, timestamp timestamp, state varchar(32), repo_revision integer, client_version varchar(32), goodcount integer, totalcount integer);
CREATE TABLE "reports_client" (
    "id" serial PRIMARY KEY,
    "creation" timestamp NOT NULL,
    "name" varchar(128) NOT NULL,
    "current_interaction_id" integer NULL REFERENCES "reports_interaction" ("id"),
    "expiration" timestamp NULL
);
CREATE TABLE "reports_metadata" (
    "id" serial PRIMARY KEY,
    "client_id" integer NOT NULL REFERENCES "reports_client" ("id"),
    "timestamp" timestamp NOT NULL
);
CREATE TABLE "reports_bad_interactions" (
    "id" serial PRIMARY KEY,
    "bad_id" integer NOT NULL REFERENCES "reports_bad" ("id"),
    "interaction_id" integer NOT NULL REFERENCES "reports_interaction" ("id"),
    UNIQUE ("bad_id", "interaction_id")
);
CREATE TABLE "reports_extra_interactions" (
    "id" serial PRIMARY KEY,
    "extra_id" integer NOT NULL REFERENCES "reports_extra" ("id"),
    "interaction_id" integer NOT NULL REFERENCES "reports_interaction" ("id"),
    UNIQUE ("extra_id", "interaction_id")
);
CREATE TABLE "reports_modified_interactions" (
    "id" serial PRIMARY KEY,
    "modified_id" integer NOT NULL REFERENCES "reports_modified" ("id"),
    "interaction_id" integer NOT NULL REFERENCES "reports_interaction" ("id"),
    UNIQUE ("modified_id", "interaction_id")
);
CREATE TABLE "reports_performance_interaction" (
    "id" serial PRIMARY KEY,
    "performance_id" integer NOT NULL REFERENCES "reports_performance" ("id"),
    "interaction_id" integer NOT NULL REFERENCES "reports_interaction" ("id"),
    UNIQUE ("performance_id", "interaction_id")
);
CREATE TABLE "reports_ping" (
    "id" serial PRIMARY KEY,
    "client_id" integer NOT NULL REFERENCES "reports_client" ("id"),
    "starttime" timestamp NOT NULL,
    "endtime" timestamp NOT NULL,
    "status" varchar(4) NOT NULL
);
COMMIT;

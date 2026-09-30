-- 앱 계정 eodiegoServer 생성 + SELECT/INSERT 권한 부여 (관리자 실행, @app_database/@app_password 변수로 전달)

SET @app_user_sql = CONCAT(
    'CREATE USER IF NOT EXISTS ''eodiegoServer''@''%'' IDENTIFIED BY ', QUOTE(@app_password)
);
PREPARE app_user_stmt FROM @app_user_sql;
EXECUTE app_user_stmt;
DEALLOCATE PREPARE app_user_stmt;

SET @app_grant_sql = CONCAT(
    'GRANT SELECT, INSERT ON `', REPLACE(@app_database, '`', '``'), '`.* TO ''eodiegoServer''@''%'''
);
PREPARE app_grant_stmt FROM @app_grant_sql;
EXECUTE app_grant_stmt;
DEALLOCATE PREPARE app_grant_stmt;

SHOW GRANTS FOR 'eodiegoServer'@'%';

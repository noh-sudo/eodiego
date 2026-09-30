-- 로컬 DB(eodiego, eodiego_test)와 앱 계정 일괄 생성 (관리자 계정으로 프로젝트 루트에서 실행)

CREATE DATABASE IF NOT EXISTS `eodiego` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `eodiego`;
source db/schema.sql

CREATE DATABASE IF NOT EXISTS `eodiego_test` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `eodiego_test`;
source db/schema.sql

SET @app_database = 'eodiego';
source db/create_app_user.sql

SET @app_database = 'eodiego_test';
source db/create_app_user.sql

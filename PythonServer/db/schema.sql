-- 어디GO 테이블 정의 (MySQL 8.0+, 관리자 실행, 앱은 추가만 하는 구조)

-- --- A: 회원 ---
CREATE TABLE IF NOT EXISTS `user` (
    `user_id`       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `username`      VARCHAR(100)    NOT NULL,
    `password_hash` VARCHAR(255)    NOT NULL,  -- PBKDF2 해시 (평문 저장 금지)
    `created_at`    DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`user_id`),
    UNIQUE KEY `uq_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --- A: 세션 (SHA-256 해시만 저장) ---
CREATE TABLE IF NOT EXISTS `session` (
    `token_hash` CHAR(64)        NOT NULL,
    `user_id`    BIGINT UNSIGNED NOT NULL,
    `expires_at` DATETIME(6)     NOT NULL,  -- UTC, 앱이 넣음
    `created_at` DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`token_hash`),
    KEY `idx_session_user` (`user_id`),
    KEY `idx_session_expires` (`expires_at`),
    CONSTRAINT `fk_session_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 로그아웃 기록 (여기 있는 세션은 만료 전이라도 무효)
CREATE TABLE IF NOT EXISTS `session_revocation` (
    `token_hash` CHAR(64)    NOT NULL,
    `revoked_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`token_hash`),
    CONSTRAINT `fk_revocation_session` FOREIGN KEY (`token_hash`) REFERENCES `session` (`token_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --- A: 저장 일정 (content_id만 참조) ---
CREATE TABLE IF NOT EXISTS `plan` (
    `plan_id`     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`     BIGINT UNSIGNED NOT NULL,
    `title`       VARCHAR(200)    NOT NULL,
    `travel_date` CHAR(8)         NOT NULL,  -- YYYYMMDD
    `created_at`  DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`plan_id`),
    KEY `idx_plan_user` (`user_id`, `created_at`),
    CONSTRAINT `fk_plan_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `plan_item` (
    `plan_item_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `plan_id`      BIGINT UNSIGNED NOT NULL,
    `content_id`   VARCHAR(20)     NOT NULL,
    `name`         VARCHAR(200)    NOT NULL,
    `item_order`   INT             NOT NULL,  -- ORDER는 예약어라 item_order 사용
    `visit_time`   CHAR(5)         NOT NULL,  -- HH:MM
    `note`         TEXT            NULL,
    PRIMARY KEY (`plan_item_id`),
    KEY `idx_plan_item_plan` (`plan_id`, `item_order`),
    CONSTRAINT `fk_plan_item_plan` FOREIGN KEY (`plan_id`) REFERENCES `plan` (`plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 일정 삭제 기록 (조회에서 제외)
CREATE TABLE IF NOT EXISTS `plan_deletion` (
    `plan_id`    BIGINT UNSIGNED NOT NULL,
    `user_id`    BIGINT UNSIGNED NOT NULL,
    `deleted_at` DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`plan_id`),
    CONSTRAINT `fk_plan_deletion_plan` FOREIGN KEY (`plan_id`) REFERENCES `plan` (`plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --- B: 관광공사 API 호출 기록 (호출 1건 = 1행) ---
CREATE TABLE IF NOT EXISTS `kto_api_call` (
    `call_id`   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `call_day`  DATE            NOT NULL,  -- 한국 시간 기준 날짜, 앱이 넣음
    `operation` VARCHAR(50)     NOT NULL,
    `called_at` DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`call_id`),
    KEY `idx_kto_call_day` (`call_day`, `operation`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --- C: LLM 요청 기록 (요청 1건 = 1행) ---
CREATE TABLE IF NOT EXISTS `llm_request` (
    `request_id`   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `request_day`  DATE            NOT NULL,  -- UTC 기준 날짜, 앱이 넣음
    `model`        VARCHAR(100)    NOT NULL,
    `requested_at` DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`request_id`),
    KEY `idx_llm_request_day` (`request_day`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- LLM 토큰 사용량 (응답 1건 = 1행)
CREATE TABLE IF NOT EXISTS `llm_token_usage` (
    `usage_id`      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `usage_day`     DATE            NOT NULL,  -- UTC 기준 날짜, 앱이 넣음
    `model`         VARCHAR(100)    NOT NULL,
    `input_tokens`  INT UNSIGNED    NOT NULL,
    `output_tokens` INT UNSIGNED    NOT NULL,
    `recorded_at`   DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`usage_id`),
    KEY `idx_llm_token_usage_day` (`usage_day`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

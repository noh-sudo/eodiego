-- 오래된 기록 정리 (관리자 계정으로 주기 실행: mysql -u <관리자> -p eodiego < db/maintenance.sql)

-- 만료된 세션 (참조하는 폐기 기록부터 삭제)
DELETE r FROM `session_revocation` r
JOIN `session` s ON s.token_hash = r.token_hash
WHERE s.expires_at < UTC_TIMESTAMP(6);

DELETE FROM `session` WHERE `expires_at` < UTC_TIMESTAMP(6);

-- 호출 기록은 최근 90일만 보관
DELETE FROM `kto_api_call`    WHERE `call_day`    < CURRENT_DATE - INTERVAL 90 DAY;
DELETE FROM `llm_request`     WHERE `request_day` < CURRENT_DATE - INTERVAL 90 DAY;
DELETE FROM `llm_token_usage` WHERE `usage_day`   < CURRENT_DATE - INTERVAL 90 DAY;

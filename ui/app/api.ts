/** D(BFF)의 /ui/* JSON API 클라이언트 (결과는 HTTP 코드가 아닌 envelope status로 분기) */

export type ErrorData = { message: string; retryable: boolean; code?: string | null };

export type Envelope<T> =
  | { status: "success"; data: T }
  | { status: "empty"; message: string }
  | { status: "error"; data: ErrorData };

export type User = { user_id: number; username: string };

/** 지역 선택지 (좌표는 B가 관리) */
export type Region = { code: string; name: string; map_x: number; map_y: number };

export type Place = {
  content_id: string;
  name: string;
  addr: string;
  map_x: number;
  map_y: number;
  dist: number;
  image: string | null;
  category?: string | null;
  use_time?: string | null;
  rest_date?: string | null;
  expected_stay_minutes?: number | null;
  overview?: string | null;
};

export type CongestionView = { has_data: boolean; rate: number | null; label: string; is_high: boolean };

export type PlanItem = {
  content_id: string;
  order: number;
  visit_time: string;
  name: string;
  note: string;
  /** note와 별개인 집중률 라벨 (note는 LLM 설명으로 덮임) */
  congestion_label: string;
  high_congestion: boolean;
  replan_prompt?: { message: string; target_name: string };
  /** 최종 일정 장소만 조회되는 상세정보 */
  detail: Place | null;
};

export type ReplanResult = { plan: PlanView; changed_content_id: string; change_reason: string };

export type PlanView = { title: string; summary: string; travel_date: string; items: PlanItem[] };

export type SavedPlanItem = { content_id: string; name: string; order: number; visit_time: string; note: string | null };
export type SavedPlan = { plan_id: number; title: string; travel_date: string; items: SavedPlanItem[] };

/** 저장 일정 상세 (current는 B 실시간 재조회 결과, 실패 시 null) */
export type PlanDetailItem = {
  content_id: string;
  name: string;
  order: number;
  visit_time: string;
  note: string | null;
  current: Place | null;
};
export type PlanDetail = { plan_id: number; title: string; travel_date: string; items: PlanDetailItem[] };

// 기본값 ""(같은 origin), 다른 호스트의 D는 NEXT_PUBLIC_BFF_BASE_URL로 지정
const BASE: string =
  (typeof process !== "undefined" && process.env && process.env.NEXT_PUBLIC_BFF_BASE_URL) || "";

const NETWORK_ERROR = { message: "서버에 연결하지 못했습니다.\n잠시 후 다시 시도해주세요.", retryable: true };

async function call<T>(path: string, method = "GET", body?: unknown): Promise<Envelope<T>> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      credentials: "include",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    return { status: "error", data: NETWORK_ERROR };
  }

  // D가 못 잡은 예외(500)나 검증 오류(422)는 envelope이 아님
  if (!res.ok) {
    return {
      status: "error",
      data: { message: `요청을 처리하지 못했습니다. (HTTP ${res.status})`, retryable: res.status >= 500 },
    };
  }
  try {
    return (await res.json()) as Envelope<T>;
  } catch {
    return { status: "error", data: NETWORK_ERROR };
  }
}

/** error/empty면 화면 문구, success면 null */
export function errorMessage(env: Envelope<unknown>): string | null {
  if (env.status === "error") return env.data.message;
  if (env.status === "empty") return env.message;
  return null;
}

/** 로그인이 필요한 실패인지 여부 */
export function needsLogin(env: Envelope<unknown>): boolean {
  return env.status === "error" && (env.data.code === "AUTH_REQUIRED" || env.data.code === "SESSION_EXPIRED");
}

// --- 인증 (A) ---
export const register = (username: string, password: string) =>
  call<User>("/ui/auth/register", "POST", { username, password });
export const login = (username: string, password: string) =>
  call<User>("/ui/auth/login", "POST", { username, password });
export const logout = () => call<null>("/ui/auth/logout", "POST", {});
export const me = () => call<User | null>("/ui/auth/me");

// --- 지역 / 관광지 / 집중률 (B) ---
export const listRegions = () => call<Region[]>("/ui/regions");
/** 반경은 B 설정값 사용 */
export const nearby = (map_x: number, map_y: number) =>
  call<Place[]>("/ui/places/nearby", "POST", { map_x, map_y });
/** 이름을 함께 넘겨 B의 상세 재조회 생략 */
export const congestion = (places: { content_id: string; name: string }[], travel_date: string) =>
  call<Record<string, CongestionView>>("/ui/places/congestion", "POST", {
    travel_date,
    targets: places.map((p) => ({ content_id: p.content_id, name: p.name })),
  });

// --- 일정 생성 (C) / 저장 (A) ---
export const generatePlan = (req: {
  map_x: number;
  map_y: number;
  travel_date: string;
  start_time: string;
  end_time: string;
  place_count: number;
  theme?: string | null;
}) => call<PlanView>("/ui/plan/generate", "POST", req);

/** 집중률이 높은 한 곳만 다른 관광지로 교체 */
export const replan = (plan: PlanView, target_content_id: string, reason: string) =>
  call<ReplanResult>("/ui/plan/replan", "POST", {
    plan: {
      title: plan.title,
      travel_date: plan.travel_date,
      summary: plan.summary,
      items: plan.items.map((i) => ({
        content_id: i.content_id,
        name: i.name,
        order: i.order,
        visit_time: i.visit_time,
        note: i.note,
        congestion_label: i.congestion_label,
        high_congestion: i.high_congestion,
        // 받아둔 상세정보를 돌려보내 C의 좌표 재조회 생략
        detail: i.detail,
      })),
    },
    target_content_id,
    reason,
  });

export const savePlan = (plan: PlanView) =>
  call<SavedPlan>("/ui/plans", "POST", {
    title: plan.title,
    travel_date: plan.travel_date,
    items: plan.items.map((i) => ({
      content_id: i.content_id,
      name: i.name,
      order: i.order,
      visit_time: i.visit_time,
      note: i.note,
    })),
  });

export const listPlans = () => call<SavedPlan[]>("/ui/plans");
export const getPlanDetail = (planId: number) => call<PlanDetail>(`/ui/plans/${planId}`);

// --- 화면 조건 -> API 파라미터 변환 ---

/** "YYYYMMDD" -> "2026.09.12" */
export const formatYmd = (ymd: string) =>
  /^\d{8}$/.test(ymd) ? `${ymd.slice(0, 4)}.${ymd.slice(4, 6)}.${ymd.slice(6)}` : ymd;

/** 기기 기준 오늘(+offsetDays)을 "YYYY-MM-DD"로 (toISOString은 UTC라 사용 안 함) */
export function localIsoDate(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** "YYYY-MM-DD" -> "YYYYMMDD" */
export const toYmd = (isoDate: string) => isoDate.replaceAll("-", "");

/** 여행 일수 -> 방문지 수 (하루치 일정이라 상한 적용) */
export function placeCountFor(startIso: string, endIso: string): number {
  const start = Date.parse(startIso);
  const end = Date.parse(endIso);
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return 3;
  const days = Math.round((end - start) / 86_400_000) + 1;
  return Math.min(8, Math.max(2, days * 2));
}

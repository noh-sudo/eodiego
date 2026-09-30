/** Cloudflare Worker 진입점 */
import handler from "vinext/server/app-router-entry";

interface Env {
  /** 정적 파일 바인딩 (public/ 제공용) */
  ASSETS: { fetch(request: Request): Promise<Response> };
  /** D(BFF) base URL, 없으면 /ui/* 프록시 안 함 */
  BFF_BASE_URL?: string;
  /** D가 요구하는 공유 시크릿 */
  BFF_GATEWAY_TOKEN?: string;
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // /ui/*는 같은 origin 유지를 위해 D로 프록시 (vinext start는 env 대신 process.env 사용)
    if (url.pathname.startsWith("/ui/")) {
      const bffBaseUrl =
        env?.BFF_BASE_URL || (typeof process !== "undefined" ? process.env?.BFF_BASE_URL : undefined);
      if (bffBaseUrl) {
        const target = new URL(url.pathname + url.search, bffBaseUrl);
        const proxied = new Request(target, request);
        // 브라우저가 보낸 같은 이름의 헤더는 덮어써 위조 방지
        const gatewayToken =
          env?.BFF_GATEWAY_TOKEN ||
          (typeof process !== "undefined" ? process.env?.BFF_GATEWAY_TOKEN : undefined);
        if (gatewayToken) proxied.headers.set("x-bff-token", gatewayToken);
        else proxied.headers.delete("x-bff-token");
        return fetch(proxied);
      }
    }

    return handler.fetch(request, env, ctx);
  },
};

export default worker;

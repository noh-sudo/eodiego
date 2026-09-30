import vinext from "vinext";
import { defineConfig } from "vite";

const localBindingConfig = {
  main: "./worker/index.ts",
  compatibility_flags: ["nodejs_compat"],
  // worker가 /ui/*를 넘길 D(BFF) 주소 (배포 시 호스팅 환경변수로 덮어씀)
  vars: {
    BFF_BASE_URL: process.env.BFF_BASE_URL ?? "",
    BFF_GATEWAY_TOKEN: process.env.BFF_GATEWAY_TOKEN ?? "",
  },
};

export default defineConfig(async () => {
  // Wrangler/Miniflare 상태를 프로젝트 안에 보관
  process.env.WRANGLER_WRITE_LOGS ??= "false";
  process.env.WRANGLER_LOG_PATH ??= ".wrangler/logs";
  process.env.MINIFLARE_REGISTRY_PATH ??= ".wrangler/registry";

  // Cloudflare 플러그인 import 시점에 로그 경로가 고정되므로 먼저 설정
  const { cloudflare } = await import("@cloudflare/vite-plugin");

  return {
    server: {
      host: "0.0.0.0",
      // /ui/*를 D로 프록시해 세션 쿠키를 같은 origin으로 유지
      proxy: {
        "/ui": {
          target: process.env.BFF_BASE_URL ?? "http://127.0.0.1:8003",
          changeOrigin: false,
          headers: process.env.BFF_GATEWAY_TOKEN
            ? { "x-bff-token": process.env.BFF_GATEWAY_TOKEN }
            : undefined,
        },
      },
    },
    plugins: [
      vinext(),
      cloudflare({
        viteEnvironment: { name: "rsc", childEnvironments: ["ssr"] },
        inspectorPort: false,
        config: localBindingConfig,
      }),
    ],
  };
});

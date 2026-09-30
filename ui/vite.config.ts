import vinext from "vinext";
import { defineConfig } from "vite";

const localBindingConfig = {
  main: "./worker/index.ts",
  compatibility_flags: ["nodejs_compat"],
  // worker가 /ui/* 를 D(BFF)로 넘길 때 쓰는 주소. 배포 환경에서는 호스팅
  // 대시보드의 환경변수로 덮어쓴다.
  vars: {
    BFF_BASE_URL: process.env.BFF_BASE_URL ?? "",
    BFF_GATEWAY_TOKEN: process.env.BFF_GATEWAY_TOKEN ?? "",
  },
};

export default defineConfig(async () => {
  // Keep Wrangler and Miniflare state project-local. These are non-secret tool
  // settings; application environment belongs in ignored `.env*` files.
  process.env.WRANGLER_WRITE_LOGS ??= "false";
  process.env.WRANGLER_LOG_PATH ??= ".wrangler/logs";
  process.env.MINIFLARE_REGISTRY_PATH ??= ".wrangler/registry";

  // Wrangler snapshots its log path while the Cloudflare plugin is imported.
  const { cloudflare } = await import("@cloudflare/vite-plugin");

  return {
    server: {
      host: "0.0.0.0",
      // 화면은 /ui/* 를 같은 origin으로 호출하고, dev 서버가 D(BFF)로 넘긴다.
      // 이렇게 해야 세션 쿠키가 cross-origin CORS 제약 없이 그대로 오간다.
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

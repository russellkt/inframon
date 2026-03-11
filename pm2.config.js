export default {
  apps: [
    {
      name: "inframon-api",
      script: "node",
      args: "dist/server.js",
      exec_mode: "fork",
      env: {
        PORT_API: "3001",
        ZABBIX_API_URL: process.env.ZABBIX_API_URL,
        ZABBIX_API_TOKEN: process.env.ZABBIX_API_TOKEN,
        OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY,
        NODE_ENV: process.env.NODE_ENV || "production",
      },
      error_file: "./logs/api.error.log",
      out_file: "./logs/api.out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
    },
    {
      name: "inframon-web-ui",
      script: "npm",
      args: "run preview",
      cwd: "/app/web-ui-app",
      exec_mode: "fork",
      env: {
        PORT: "3000",
        NODE_ENV: process.env.NODE_ENV || "production",
      },
      error_file: "./logs/web-ui.error.log",
      out_file: "./logs/web-ui.out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
    },
  ],
};

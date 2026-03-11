export default {
  apps: [
    {
      name: "inframon-agent",
      script: "pi",
      args: 'daemon --agent inframon --poll-interval 300',
      exec_mode: "fork",
      env: {
        ZABBIX_API_TOKEN: process.env.ZABBIX_API_TOKEN,
        ZABBIX_API_URL: process.env.ZABBIX_API_URL,
        PROXMOX_HOST: process.env.PROXMOX_HOST,
        PROXMOX_USER: process.env.PROXMOX_USER,
        PROXMOX_TOKEN_ID: process.env.PROXMOX_TOKEN_ID,
        PROXMOX_TOKEN_SECRET: process.env.PROXMOX_TOKEN_SECRET,
        PROXMOX_VERIFY_SSL: process.env.PROXMOX_VERIFY_SSL || "false",
        NODE_ENV: process.env.NODE_ENV || "production",
      },
      error_file: "./logs/inframon-agent.error.log",
      out_file: "./logs/inframon-agent.out.log",
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

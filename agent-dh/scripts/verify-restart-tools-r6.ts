/**
 * verify-restart-tools-r6.ts
 * Round 6 新鲜进程验证：quantsys_v2_restart + agent_os_restart（真实重启，非 dry-run）
 * 背景：用户授权实测两个重启工具。
 *  - quantsys_v2_restart 曾报「工具执行失败」：根因 = v2-api 由 launchd 托管（KeepAlive），
 *    旧 kill+spawn 流程在 kill 后被 launchd 抢先拉起，端口「永不释放」→ 误报失败。
 *    已修复为 launchctl kickstart -k 权威重启（launchd 不可用才回退旧流程）。
 *  - agent_os_restart 已（2026-08-28）为 launchd kickstart 模式，本 harness 一并实测。
 * 验证链：tool.call() → toDSHToolDefinition().execute() → snapshotJsonValue(lossless)
 *        → validateJsonSchemaValue(schema) → output.render()
 * 独立进程运行；结束后 curl 健康端点 + lsof 确认服务恢复。
 */
import { execSync } from 'child_process';
import * as dshSession from '@deepseek-ai/dsh-session';
import * as dshTools from '@deepseek-ai/dsh-tools';

import { QuantsysV2RestartTool } from '../packages/quantsys-v2-manager/src/tools/QuantsysV2RestartTool/QuantsysV2RestartTool';
import { AgentOsRestartTool } from '../packages/agent-os-manager/src/tools/AgentOsRestartTool/AgentOsRestartTool';

const snapshotJsonValue: any = (dshSession as any).snapshotJsonValue ?? (dshSession as any).default?.snapshotJsonValue;
const validateJsonSchemaValue: any = (dshTools as any).validateJsonSchemaValue;
if (!snapshotJsonValue || !validateJsonSchemaValue) {
  console.error('FATAL: dsh-session/dsh-tools 导出缺失');
  process.exit(2);
}

const QV2_CONFIG = {
  projectRoot: '/Users/yunpeng/pi-investment/quantsys-v2',
  port: 5001,
  healthCheckUrl: 'http://localhost:5001/api/health',
  startupScript: 'adapters/inbound/fastapi_app/main.py',
  activateScript: 'activate-py313.sh',
  logFile: 'logs/launchd-stdout.log',
  launchdLabel: 'com.pi-investment.v2-api',
};
const AOS_CONFIG = {
  projectRoot: '/Users/yunpeng/pi-investment/agent-os',
  port: 8080,
  healthCheckUrl: 'http://localhost:8080/health',
  startCommand: './bin/agent-os serve',
  logDir: 'logs',
  launchdLabel: 'com.pi-investment.agent-os',
};

function pidOn(port: number): number | null {
  try {
    const s = execSync(`lsof -ti:${port} -sTCP:LISTEN`, { encoding: 'utf-8', timeout: 3000 }).trim();
    return s ? parseInt(s) : null;
  } catch {
    return null;
  }
}

async function runCase(name: string, tool: any, args: any): Promise<{ ok: boolean; steps: any[]; final: any; detail: string }> {
  const started = Date.now();
  const res: any = await tool.call(args);
  if (!res?.success) {
    return { ok: false, steps: [], final: null, detail: JSON.stringify(res?.error ?? res).slice(0, 400) };
  }
  const def: any = tool.toDSHToolDefinition();
  let data: any;
  try {
    data = await def.execute(args);
  } catch (e: any) {
    return { ok: false, steps: [], final: null, detail: 'def.execute: ' + String(e?.message ?? e).slice(0, 300) };
  }
  const snapped = snapshotJsonValue(data);
  if (snapped === undefined) {
    return { ok: false, steps: [], final: null, detail: 'snapshotJsonValue 拒绝输出（lossless 问题）' };
  }
  const schema: any = tool.getPrompt?.().output?.schema;
  let schemaErrors: string[] = [];
  if (schema) {
    try { schemaErrors = validateJsonSchemaValue(schema, snapped); } catch (e2: any) { schemaErrors = ['schema 校验抛异常: ' + String(e2?.message ?? e2)]; }
  }
  if (schemaErrors.length > 0) {
    return { ok: false, steps: [], final: null, detail: 'schema 校验失败: ' + schemaErrors.slice(0, 5).join(' | ') };
  }
  const rendered = def.output.render(args, snapped);
  if (!Array.isArray(rendered) || rendered.length === 0) {
    return { ok: false, steps: [], final: null, detail: 'render 无输出' };
  }
  return {
    ok: true,
    steps: data?.steps ?? [],
    final: data?.final_status ?? null,
    detail: 'OK ' + (Date.now() - started) + 'ms',
  };
}

async function main() {
  console.log('== Round 6 重启工具实测 ==', new Date().toISOString());
  console.log('重启前 PID :5001 =', pidOn(5001), ' :8080 =', pidOn(8080));

  const results: any[] = [];

  // 1) quantsys_v2_restart（修复后 launchd kickstart 路径）
  const q = await runCase('quantsys_v2_restart', new QuantsysV2RestartTool(QV2_CONFIG), { force: false, wait_startup_sec: 30 });
  results.push({ name: 'quantsys_v2_restart', ok: q.ok, detail: q.detail });
  console.log('quantsys_v2_restart:', q.ok ? 'PASS' : 'FAIL', q.detail);
  console.log('  steps:', JSON.stringify(q.steps));
  console.log('  final_status:', JSON.stringify(q.final));

  // 2) agent_os_restart（launchd kickstart 模式）
  const a = await runCase('agent_os_restart', new AgentOsRestartTool(AOS_CONFIG), { force: false, wait_startup_sec: 30 });
  results.push({ name: 'agent_os_restart', ok: a.ok, detail: a.detail });
  console.log('agent_os_restart:', a.ok ? 'PASS' : 'FAIL', a.detail);
  console.log('  steps:', JSON.stringify(a.steps));
  console.log('  final_status:', JSON.stringify(a.final));

  // 3) 重启后服务恢复确认
  await new Promise(r => setTimeout(r, 3000));
  const p5001 = pidOn(5001), p8080 = pidOn(8080);
  let h5001 = 'down', h8080 = 'down';
  try { h5001 = execSync('curl -sf --max-time 5 http://localhost:5001/api/health', { encoding: 'utf-8', timeout: 6000 }).slice(0, 120); } catch {}
  try { h8080 = execSync('curl -sf --max-time 5 http://localhost:8080/health', { encoding: 'utf-8', timeout: 6000 }).slice(0, 120); } catch {}
  console.log('重启后 PID :5001 =', p5001, ' :8080 =', p8080);
  console.log('health :5001 =', h5001);
  console.log('health :8080 =', h8080);

  const postOk = p5001 !== null && p8080 !== null;
  results.push({ name: 'post_restart_health', ok: postOk, detail: `:5001=${h5001} :8080=${h8080}` });

  const allOk = results.every(r => r.ok);
  console.log('\n== 汇总 ==');
  for (const r of results) console.log(' ', r.ok ? 'PASS' : 'FAIL', r.name, '-', r.detail);
  process.exit(allOk ? 0 : 1);
}

main().catch(e => {
  console.error('harness fatal:', e);
  process.exit(2);
});

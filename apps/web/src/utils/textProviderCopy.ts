import type { TextProviderStatus } from "../types/workflows";

export function systemPromptTraceLine(
  status?: TextProviderStatus | null,
): string {
  if (!status?.uses_full_system_prompt) {
    return "系统规则：未载入完整主文件，请先到设置页检查系统规则状态。";
  }
  return "系统规则：完整 V7 主文件已接入本次 AI 请求。";
}

export function textProviderConfirmationNotice(
  status: TextProviderStatus | null | undefined,
  taskName: string,
  outputScope = "只生成文字分析/建议，不生成图片，不提交视频。",
): string {
  return [
    `本次将发送给：${status?.mode_label ?? "AI 分析服务"}`,
    systemPromptTraceLine(status),
    `当前任务：${taskName}`,
    `结果范围：${outputScope}`,
    "可能产生文本模型费用，请确认本次请求。",
  ].join("\n");
}

const replacements: Array<[RegExp, string]> = [
  [/VP-PRECISION-18/g, "分镜提示词"],
  [/分镜视频提示词/g, "分镜提示词"],
  [/视频提示词/g, "分镜提示词"],
  [/最终视频/g, "成片"],
  [/FLOW-NAV/g, "流程导航"],
  [/Provider/g, "服务"],
  [/provider/g, "服务"],
  [/Storyboard Grid/g, "故事板格数"],
  [/Grid Reason/g, "为什么选这个格数"],
  [/Prompt Match/g, "对应的视频时间段"],
  [/Storyboard Execution Page/g, "故事板总览页"],
  [/导演草案/g, "故事板参考提示词"],
  [/正式执行包/g, "成片提示词"],
  [/final_execution/g, "成片提示词"],
  [/director_draft/g, "故事板参考提示词"],
  [/huimeng_chat/g, "慧梦文本通道"],
  [/openai_responses/g, "OpenAI 官方文本通道"],
  [/schema_version/g, "资料格式版本"],
  [/package_stage/g, "资料阶段"],
  [/\bready\b/g, "可提交"],
  [/\bblocked\b/g, "被拦住"],
  [/\bdraft\b/g, "草稿"],
  [/\bsubmitted\b/g, "已提交"],
  [/\bprocessing\b/g, "生成中"],
  [/\bcompleted\b/g, "已完成"],
  [/\bfailed\b/g, "失败"],
  [/\bimported\b/g, "已导入"],
  [/\blegacy\b/g, "旧版记录"],
  [/\bOpenAI\b/g, "OpenAI"],
  [/\bAPI\b/g, "API"],
  [/\bUCODE-9\b/g, "UCODE-9"],
];

export function humanizeCopy(value: unknown): string {
  let text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const lowered = text.toLowerCase();
  if (
    lowered.includes("server disconnected without sending a response") ||
    lowered.includes("remoteprotocolerror") ||
    lowered.includes("peer closed connection") ||
    lowered.includes("connection reset")
  ) {
    return "AI 服务在返回结果前中断了连接。项目和已保存资料没有损坏，但本次没有取得可保存的分析结果。为避免重复请求可能产生两次费用，系统没有自动重试。请稍后手动点击“从剧本识别资产”；如果连续出现，请到“成本与设置”切换文本服务，或缩短本次处理的剧本范围。";
  }
  if (text.includes("504") || lowered.includes("gateway time")) {
    return "AI 分析服务超时（504）。通常是服务商接口繁忙或本次输入较长，不是你的项目坏了。请稍后重试；如果连续失败，可以先缩短输入范围，或到“成本与设置”切换文本服务。";
  }
  if (lowered.includes("timeout") || lowered.includes("timed out")) {
    return "AI 分析请求超时。请稍后重试；如果连续失败，建议缩短输入文本或切换服务。";
  }
  if (text.includes("401") || lowered.includes("unauthorized")) {
    return "AI 分析鉴权失败。请到“成本与设置”检查 API Key 是否正确。";
  }
  if (
    text.includes("429") ||
    lowered.includes("rate limit") ||
    lowered.includes("too many")
  ) {
    return "AI 分析请求过于频繁或额度受限。请稍后重试，或检查服务商额度。";
  }
  for (const [pattern, replacement] of replacements) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

export function stageName(stage: string): string {
  if (stage === "director_draft") return "故事板参考提示词";
  if (stage === "final_execution") return "成片提示词";
  return humanizeCopy(stage);
}

export function versionStateName(status: string): string {
  const names: Record<string, string> = {
    draft: "待确认",
    confirmed_current: "已确认",
    confirmed_history: "历史版本",
    locked: "已锁定",
    rejected: "已拒绝",
    ready: "可提交",
    blocked: "还不能提交",
    awaiting_budget_confirm: "等待费用确认",
    submitted: "已提交",
    processing: "生成中",
    completed: "已完成",
    failed: "失败",
    imported: "已导入",
  };
  return names[status] ?? humanizeCopy(status);
}

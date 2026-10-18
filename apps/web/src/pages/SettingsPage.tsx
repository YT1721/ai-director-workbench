import { useEffect, useState, type ReactNode } from "react";
import {
  Brain,
  CheckCircle2,
  CircleAlert,
  KeyRound,
  ShieldCheck,
} from "lucide-react";

import {
  fetchJimengCliStatus,
  fetchLiveProviderStatus,
  fetchLocalEnvStatus,
  fetchSeedanceSkillStatus,
  fetchSystemPromptStatus,
  fetchTextProviderStatus,
  updateLocalEnv,
} from "../services/api";
import {
  DirectorStatusPanel,
  DirectorWorkbenchFrame,
  GuidePrimaryButton,
  GuideProgressToast,
  TechDetails,
  type DirectorStageItem,
} from "../components/Guide";
import { workbenchPageClass } from "../styles/layout";
import type { JimengCliStatus, LiveProviderStatus } from "../types/videos";
import type { LocalEnvStatus, TextProviderStatus } from "../types/workflows";
import type { SeedanceSkillStatus, SystemPromptStatus } from "../types/system";

const inputClass =
  "mt-2 w-full border border-white/15 bg-[#11171c] px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-orange-400/70";

type TextServicePreset = {
  id: string;
  label: string;
  baseUrl: string;
  model: string;
  keyHint: string;
};

const TEXT_SERVICE_PRESETS: TextServicePreset[] = [
  {
    id: "huimeng",
    label: "慧梦（当前在用）",
    baseUrl: "https://api.huimengi.com/v1",
    model: "gpt-5.5",
    keyHint: "慧梦控制台生成的 Key，与生图/视频共用同一个。",
  },
  {
    id: "kimi",
    label: "Kimi（月之暗面）",
    baseUrl: "https://api.moonshot.cn/v1",
    model: "kimi-k2-0905-preview",
    keyHint: "到 platform.moonshot.cn 创建 API Key。",
  },
  {
    id: "deepseek",
    label: "DeepSeek",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    keyHint: "到 platform.deepseek.com 创建 API Key。",
  },
  {
    id: "glm",
    label: "智谱 GLM",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-plus",
    keyHint: "到 open.bigmodel.cn 创建 API Key。",
  },
  {
    id: "gemini",
    label: "Gemini（Google）",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    model: "gemini-2.5-pro",
    keyHint: "到 aistudio.google.com 创建 API Key。",
  },
  {
    id: "custom",
    label: "自定义（兼容 OpenAI 格式的服务）",
    baseUrl: "",
    model: "",
    keyHint: "填写服务商提供的 Key。",
  },
];

function inferTextPresetId(baseUrl: string): string {
  const matched = TEXT_SERVICE_PRESETS.find(
    (preset) =>
      preset.baseUrl && preset.baseUrl === baseUrl.replace(/\/+$/, ""),
  );
  return matched?.id ?? "custom";
}

const initialEnvForm = {
  openaiApiKey: "",
  openaiTextModel: "",
  openaiImageModel: "",
  openaiMaxOutputTokens: "4000",
  textProviderMode: "huimeng_chat",
  textServicePreset: "huimeng",
  textApiKey: "",
  textBaseUrl: "https://api.huimengi.com/v1",
  textModel: "gpt-5.5",
  enableRealTextAnalysis: false,
  enableRealOpenai: false,
  enableRealImageGeneration: false,
  huimengiApiKey: "",
  huimengiTextBaseUrl: "https://api.huimengi.com/v1",
  huimengiTextModel: "gpt-5.5",
  imageProviderMode: "huimeng_tasks",
  imageApiKey: "",
  imageBaseUrl: "",
  imageModel: "",
  huimengiImageBaseUrl: "https://api.huimengi.com",
  huimengiImageModel: "image-2",
  huimengiVideoBaseUrl: "https://api.huimengi.com",
  huimengiVideoModel: "seedance-2.0-fast",
  enableRealSeedance: false,
  videoProviderMode: "jimeng_cli",
};

function StatusPill({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 border px-2.5 py-1 text-xs ${
        ok
          ? "border-emerald-400/40 bg-emerald-400/8 text-emerald-200"
          : "border-amber-400/40 bg-amber-400/8 text-amber-200"
      }`}
    >
      {ok ? <CheckCircle2 size={13} /> : <CircleAlert size={13} />}
      {children}
    </span>
  );
}

function SummaryCard({
  title,
  ok,
  detail,
}: {
  title: string;
  ok: boolean;
  detail: string;
}) {
  return (
    <div
      className={`border p-4 ${ok ? "border-emerald-400/25 bg-emerald-400/7" : "border-amber-400/25 bg-amber-400/7"}`}
    >
      <StatusPill ok={ok}>{ok ? "已就绪" : "待配置"}</StatusPill>
      <h3 className="mt-3 text-base font-semibold text-zinc-100">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-zinc-400">{detail}</p>
    </div>
  );
}

export function SettingsPage() {
  const [systemStatus, setSystemStatus] = useState<SystemPromptStatus | null>(
    null,
  );
  const [seedanceSkillStatus, setSeedanceSkillStatus] =
    useState<SeedanceSkillStatus | null>(null);
  const [textStatus, setTextStatus] = useState<TextProviderStatus | null>(null);
  const [localEnv, setLocalEnv] = useState<LocalEnvStatus | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveProviderStatus | null>(null);
  const [jimengCli, setJimengCli] = useState<JimengCliStatus | null>(null);
  const [envForm, setEnvForm] = useState(initialEnvForm);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const showDevTools = import.meta.env.VITE_SHOW_DEV_TOOLS === "true";

  const applyLocalStatusToForm = (status: LocalEnvStatus) => {
    setEnvForm((current) => ({
      ...current,
      openaiApiKey: "",
      openaiTextModel: status.openai_text_model || status.openai_model_routine,
      openaiImageModel: status.openai_image_model,
      openaiMaxOutputTokens: String(status.openai_max_output_tokens || 4000),
      textProviderMode: ["huimeng_chat", "openai_responses"].includes(
        status.text_provider_mode,
      )
        ? status.text_provider_mode
        : "huimeng_chat",
      textServicePreset: inferTextPresetId(
        status.text_base_url || status.huimengi_text_base_url || "",
      ),
      textApiKey: "",
      textBaseUrl:
        status.text_base_url ||
        status.huimengi_text_base_url ||
        "https://api.huimengi.com/v1",
      textModel: status.text_model || status.huimengi_text_model || "gpt-5.5",
      enableRealTextAnalysis: status.enable_real_text_analysis,
      enableRealOpenai: status.enable_real_openai,
      enableRealImageGeneration: status.enable_real_image_generation,
      huimengiApiKey: "",
      huimengiTextBaseUrl:
        status.huimengi_text_base_url || "https://api.huimengi.com/v1",
      huimengiTextModel: status.huimengi_text_model || "gpt-5.5",
      imageProviderMode: ["huimeng_tasks", "openai_images"].includes(
        status.image_provider_mode,
      )
        ? status.image_provider_mode
        : "huimeng_tasks",
      imageApiKey: "",
      imageBaseUrl: status.image_base_url || "",
      imageModel: status.image_model || "",
      huimengiImageBaseUrl:
        status.huimengi_image_base_url || "https://api.huimengi.com",
      huimengiImageModel: status.huimengi_image_model || "image-2",
      huimengiVideoBaseUrl:
        status.huimengi_video_base_url ||
        status.huimengi_base_url ||
        "https://api.huimengi.com",
      huimengiVideoModel:
        status.huimengi_video_model ||
        status.huimengi_model_id ||
        "seedance-2.0-fast",
      enableRealSeedance: status.enable_real_seedance,
      videoProviderMode: [
        "huimeng_live",
        "jimeng_cli",
        "volcengine_seedance25",
      ].includes(status.video_provider_mode)
        ? status.video_provider_mode
        : "jimeng_cli",
    }));
  };

  const refresh = async () => {
    const [prompt, skill, text, env, live, cli] = await Promise.all([
      fetchSystemPromptStatus(),
      fetchSeedanceSkillStatus(),
      fetchTextProviderStatus(),
      fetchLocalEnvStatus(),
      fetchLiveProviderStatus(),
      fetchJimengCliStatus(),
    ]);
    setSystemStatus(prompt);
    setSeedanceSkillStatus(skill);
    setTextStatus(text);
    setLocalEnv(env);
    setLiveStatus(live);
    setJimengCli(cli);
    applyLocalStatusToForm(env);
  };

  useEffect(() => {
    void refresh();
  }, []);

  const saveLocalEnv = async () => {
    setError("");
    setMessage("");
    setSaving(true);
    try {
      const status = await updateLocalEnv({
        confirm_local_env_write: true,
        openai_api_key: envForm.openaiApiKey,
        openai_text_model: envForm.openaiTextModel,
        openai_model_routine: envForm.openaiTextModel,
        openai_image_model: envForm.openaiImageModel,
        openai_max_output_tokens: Number(envForm.openaiMaxOutputTokens) || 4000,
        text_provider_mode: envForm.textProviderMode,
        text_api_key: envForm.textApiKey,
        text_base_url: envForm.textBaseUrl,
        text_model: envForm.textModel,
        enable_real_text_analysis: envForm.enableRealTextAnalysis,
        enable_real_openai: envForm.enableRealOpenai,
        enable_real_image_generation: envForm.enableRealImageGeneration,
        huimengi_api_key: envForm.huimengiApiKey,
        image_provider_mode: envForm.imageProviderMode,
        image_api_key:
          envForm.imageProviderMode === "openai_images"
            ? envForm.imageApiKey
            : "",
        image_base_url:
          envForm.imageProviderMode === "openai_images"
            ? envForm.imageBaseUrl
            : "",
        image_model:
          envForm.imageProviderMode === "openai_images"
            ? envForm.imageModel
            : "",
        huimengi_image_base_url: envForm.huimengiImageBaseUrl,
        huimengi_image_model: envForm.huimengiImageModel,
        huimengi_video_base_url: envForm.huimengiVideoBaseUrl,
        huimengi_video_model: envForm.huimengiVideoModel,
        huimengi_base_url: envForm.huimengiVideoBaseUrl,
        huimengi_model_id: envForm.huimengiVideoModel,
        enable_real_seedance: envForm.enableRealSeedance,
        video_provider_mode: envForm.videoProviderMode,
      });
      setLocalEnv(status);
      applyLocalStatusToForm(status);
      await refresh();
      setMessage(
        "已保存到本机 .env。密钥不会显示在页面上；真实生成仍需要在任务页逐次确认。",
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const settingsStageItems: DirectorStageItem[] = [
    {
      title: "规则文件",
      detail: systemStatus?.loaded ? "V7 主系统已载入" : "等待后端载入主系统",
      status: systemStatus?.loaded ? "done" : "blocked",
    },
    {
      title: "文字创作",
      detail: textStatus?.ready ? textStatus.mode_label : "填写 Key 与文本模型",
      status: textStatus?.ready ? "done" : "current",
    },
    {
      title: "图片生成",
      detail: localEnv?.enable_real_image_generation
        ? `已开启：${localEnv.huimengi_image_model || "image-2"}`
        : "按需开启真实生图",
      status:
        localEnv?.enable_real_image_generation &&
        localEnv?.huimengi_api_key_configured
          ? "done"
          : "pending",
    },
    {
      title: "视频生成",
      detail: localEnv?.enable_real_seedance
        ? `已开启：${localEnv.huimengi_video_model || localEnv.huimengi_model_id || "seedance"}`
        : "按需开启真实视频",
      status:
        localEnv?.enable_real_seedance && localEnv?.huimengi_api_key_configured
          ? "done"
          : "pending",
    },
    {
      title: "即梦 CLI",
      detail: jimengCli?.ready
        ? "本机 CLI 可用"
        : jimengCli?.blocking_reason || "可选通道，未就绪",
      status: jimengCli?.ready ? "done" : "pending",
    },
  ];

  return (
    <div className={workbenchPageClass}>
      {saving ? <GuideProgressToast label="正在保存服务设置，请稍等…" /> : null}
      <section className="border border-white/12 bg-[#151b21]/90 p-7">
        <p className="text-xs tracking-[0.18em] text-orange-400">设置</p>
        <div className="mt-2 flex items-start justify-between gap-6">
          <div>
            <h1 className="text-4xl font-semibold tracking-wide text-zinc-100">
              AI 服务设置
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
              这里只配置系统要用的 API Key
              和模型。创作过程、分析结果、故事板和分镜提示词都回到主流程页面查看。
            </p>
          </div>
          <div className="rounded-full border border-emerald-400/35 bg-emerald-400/8 px-4 py-2 text-sm text-emerald-100">
            正式模式：只用真实 AI 结果
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4 xl:grid-cols-4">
          <SummaryCard
            title="系统规则"
            ok={Boolean(systemStatus?.loaded)}
            detail={
              systemStatus?.loaded
                ? "V7 主系统已载入，真实文本分析会使用当前规则。"
                : "未载入系统规则，请先启动后端。"
            }
          />
          <SummaryCard
            title="AI 分析"
            ok={Boolean(textStatus?.ready)}
            detail={
              textStatus?.ready
                ? textStatus.mode_label
                : textStatus?.blocking_reason || "请配置文本模型与 API Key。"
            }
          />
          <SummaryCard
            title="视频导演技能层"
            ok={Boolean(
              seedanceSkillStatus?.installed &&
              seedanceSkillStatus?.license_present,
            )}
            detail={
              seedanceSkillStatus?.installed
                ? `已固定版本 ${seedanceSkillStatus.pinned_commit.slice(0, 8)}，载入 ${seedanceSkillStatus.module_count} 个按需模块。`
                : "Seedance Skill OS 尚未完整安装，视频提示词仍会被阻止进入正式编译。"
            }
          />
          <SummaryCard
            title="图像 / 视频"
            ok={Boolean(localEnv?.huimengi_api_key_configured)}
            detail={
              localEnv?.huimengi_api_key_configured
                ? `生图 ${localEnv.huimengi_image_model || "image-2"}｜视频 ${localEnv.huimengi_video_model || localEnv.huimengi_model_id || "seedance-2.0-fast"}`
                : "请配置慧梦 Key 和图像 / 视频模型。"
            }
          />
        </div>
      </section>

      <div className="mt-6">
        <DirectorWorkbenchFrame
          main={
            <div className="space-y-6">
              <section className="border border-sky-400/25 bg-[#151b21] p-6">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 text-sky-300">
                      <Brain size={18} />
                      <h2 className="text-xl font-semibold">
                        AI 分析主脑（文字）
                      </h2>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">
                      剧本分析、导演方案、资产识别都走这个文字服务。选好服务商、填入对应
                      Key 即可切换；Key 留空表示不修改旧值。
                    </p>
                  </div>
                  <StatusPill ok={Boolean(textStatus?.ready)}>
                    {textStatus?.ready
                      ? `${textStatus.text_service_label || "文字服务"} 可用`
                      : "文字服务待配置"}
                  </StatusPill>
                </div>

                <div className="mt-6 grid grid-cols-2 gap-4">
                  <label className="col-span-2 text-sm text-zinc-400">
                    文字服务
                    <select
                      aria-label="文字服务"
                      className={inputClass}
                      value={envForm.textServicePreset}
                      onChange={(event) => {
                        const preset =
                          TEXT_SERVICE_PRESETS.find(
                            (item) => item.id === event.target.value,
                          ) ?? TEXT_SERVICE_PRESETS[0];
                        setEnvForm((current) => ({
                          ...current,
                          textServicePreset: preset.id,
                          textBaseUrl: preset.baseUrl || current.textBaseUrl,
                          textModel: preset.model || current.textModel,
                        }));
                      }}
                    >
                      {TEXT_SERVICE_PRESETS.map((preset) => (
                        <option key={preset.id} value={preset.id}>
                          {preset.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="col-span-2 text-sm text-zinc-400">
                    文字服务 API Key
                    <input
                      className={inputClass}
                      type="password"
                      autoComplete="off"
                      placeholder="留空则不修改"
                      value={envForm.textApiKey}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          textApiKey: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="text-sm text-zinc-400">
                    服务地址（Base URL）
                    <input
                      aria-label="文字服务地址"
                      className={inputClass}
                      value={envForm.textBaseUrl}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          textBaseUrl: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="text-sm text-zinc-400">
                    模型
                    <input
                      aria-label="文字服务模型"
                      className={inputClass}
                      value={envForm.textModel}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          textModel: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
                <p className="mt-3 text-xs leading-5 text-zinc-500">
                  {
                    TEXT_SERVICE_PRESETS.find(
                      (item) => item.id === envForm.textServicePreset,
                    )?.keyHint
                  }
                  模型名可改，填服务商支持的任意模型。切换服务后，建议先点下方"保存配置"，再回开始页做一次分析验证。
                </p>
              </section>

              <section className="border border-orange-400/25 bg-[#151b21] p-6">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 text-orange-300">
                      <KeyRound size={18} />
                      <h2 className="text-xl font-semibold">
                        慧梦 / 绘梦配置（生图与视频）
                      </h2>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">
                      这里只配置图片和视频生成用的慧梦通道；文字分析主脑在上方单独配置。Key
                      留空表示不修改旧值。
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <StatusPill
                      ok={Boolean(localEnv?.huimengi_api_key_configured)}
                    >
                      慧梦 Key{" "}
                      {localEnv?.huimengi_api_key_configured
                        ? "已配置"
                        : "未配置"}
                    </StatusPill>
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-2 gap-4">
                  <label className="col-span-2 text-sm text-zinc-400">
                    慧梦 API Key
                    <input
                      className={inputClass}
                      type="password"
                      autoComplete="off"
                      placeholder="留空则不修改"
                      value={envForm.huimengiApiKey}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          huimengiApiKey: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="col-span-2 text-sm text-zinc-400">
                    生图服务
                    <select
                      aria-label="生图服务"
                      className={inputClass}
                      value={envForm.imageProviderMode}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          imageProviderMode: event.target.value,
                        }))
                      }
                    >
                      <option value="huimeng_tasks">
                        慧梦任务制（当前在用，提交后需查询下载）
                      </option>
                      <option value="openai_images">
                        OpenAI 兼容图像 API（即时返回，一次请求直接出图）
                      </option>
                    </select>
                  </label>
                  {envForm.imageProviderMode === "openai_images" ? (
                    <>
                      <label className="col-span-2 text-sm text-zinc-400">
                        生图 API Key（即时 API 专用）
                        <input
                          className={inputClass}
                          type="password"
                          autoComplete="off"
                          placeholder="留空则不修改"
                          value={envForm.imageApiKey}
                          onChange={(event) =>
                            setEnvForm((current) => ({
                              ...current,
                              imageApiKey: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label className="text-sm text-zinc-400">
                        生图 Base URL（即时 API）
                        <input
                          className={inputClass}
                          placeholder="例如 https://api.openai.com/v1"
                          value={envForm.imageBaseUrl}
                          onChange={(event) =>
                            setEnvForm((current) => ({
                              ...current,
                              imageBaseUrl: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label className="text-sm text-zinc-400">
                        生图模型（即时 API）
                        <input
                          className={inputClass}
                          placeholder="例如 gpt-image-1"
                          value={envForm.imageModel}
                          onChange={(event) =>
                            setEnvForm((current) => ({
                              ...current,
                              imageModel: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </>
                  ) : (
                    <>
                      <label className="text-sm text-zinc-400">
                        生图 Base URL
                        <input
                          className={inputClass}
                          value={envForm.huimengiImageBaseUrl}
                          onChange={(event) =>
                            setEnvForm((current) => ({
                              ...current,
                              huimengiImageBaseUrl: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label className="text-sm text-zinc-400">
                        生图模型
                        <input
                          className={inputClass}
                          value={envForm.huimengiImageModel}
                          onChange={(event) =>
                            setEnvForm((current) => ({
                              ...current,
                              huimengiImageModel: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </>
                  )}
                  <label className="col-span-2 text-sm text-zinc-400">
                    新任务默认视频服务
                    <select
                      aria-label="视频服务"
                      className={inputClass}
                      value={envForm.videoProviderMode}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          videoProviderMode: event.target.value,
                        }))
                      }
                    >
                      <option value="jimeng_cli">
                        即梦 CLI（默认，使用本机账号积分）
                      </option>
                      <option value="volcengine_seedance25">
                        火山方舟 Seedance 2.5（首期 Mock，不发送请求）
                      </option>
                      <option value="huimeng_live">
                        慧梦 Seedance 聚合 API（按条计费）
                      </option>
                    </select>
                  </label>
                  <p className="col-span-2 text-xs leading-5 text-zinc-500">
                    这里只决定新建视频队列的默认值；进入“批量视频”后，可为本次队列独立选择慧梦
                    API、即梦 CLI 或 Seedance 2.5 Mock。
                  </p>
                  {envForm.videoProviderMode === "jimeng_cli" ? (
                    <p className="col-span-2 border border-white/10 bg-black/10 px-4 py-3 text-sm leading-6 text-zinc-400">
                      即梦 CLI 通道使用你电脑上已安装并登录的 dreamina
                      命令，不需要在这里填 Key；系统只采用当前 CLI
                      帮助中明确开放的模型，不会把网页模型冒充为 CLI 能力。
                    </p>
                  ) : envForm.videoProviderMode === "volcengine_seedance25" ? (
                    <p className="col-span-2 border border-cyan-400/25 bg-cyan-400/7 px-4 py-3 text-sm leading-6 text-cyan-100">
                      首期只运行 Seedance 2.5 本地 Mock：不读取
                      Key、不发送火山方舟请求、不扣费，也不生成伪造视频。真实
                      API 需在下一 Milestone 单独确认后开放。
                    </p>
                  ) : (
                    <>
                      <label className="text-sm text-zinc-400">
                        视频 Base URL
                        <input
                          className={inputClass}
                          value={envForm.huimengiVideoBaseUrl}
                          onChange={(event) =>
                            setEnvForm((current) => ({
                              ...current,
                              huimengiVideoBaseUrl: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label className="text-sm text-zinc-400">
                        视频模型
                        <input
                          aria-label="慧梦视频模型"
                          className={inputClass}
                          value={envForm.huimengiVideoModel}
                          onChange={(event) =>
                            setEnvForm((current) => ({
                              ...current,
                              huimengiVideoModel: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </>
                  )}
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3">
                  <label className="flex items-center gap-3 border border-white/10 bg-black/10 px-4 py-3 text-sm text-zinc-300">
                    <input
                      type="checkbox"
                      checked={envForm.enableRealImageGeneration}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          enableRealImageGeneration: event.target.checked,
                        }))
                      }
                    />
                    允许真实生图（仍需逐次确认）
                  </label>
                  {envForm.videoProviderMode === "huimeng_live" ? (
                    <label className="flex items-center gap-3 border border-white/10 bg-black/10 px-4 py-3 text-sm text-zinc-300">
                      <input
                        type="checkbox"
                        checked={envForm.enableRealSeedance}
                        onChange={(event) =>
                          setEnvForm((current) => ({
                            ...current,
                            enableRealSeedance: event.target.checked,
                          }))
                        }
                      />
                      允许真实单镜视频（仍需逐次确认）
                    </label>
                  ) : null}
                </div>
              </section>

              <details className="mt-6 border border-white/12 bg-[#151b21]/80">
                <summary className="cursor-pointer px-5 py-4 text-sm font-medium text-zinc-300 hover:text-zinc-100">
                  OpenAI 官方配置（可选）
                </summary>
                <div className="grid grid-cols-2 gap-4 border-t border-white/10 p-5">
                  <label className="col-span-2 text-sm text-zinc-400">
                    OpenAI API Key
                    <input
                      className={inputClass}
                      type="password"
                      autoComplete="off"
                      placeholder="留空则不修改"
                      value={envForm.openaiApiKey}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          openaiApiKey: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="text-sm text-zinc-400">
                    OpenAI 文本模型
                    <input
                      className={inputClass}
                      placeholder="例如：gpt-5.5 或官方模型 ID"
                      value={envForm.openaiTextModel}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          openaiTextModel: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="text-sm text-zinc-400">
                    OpenAI 生图模型
                    <input
                      className={inputClass}
                      placeholder="填写官方图像模型 ID"
                      value={envForm.openaiImageModel}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          openaiImageModel: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="text-sm text-zinc-400">
                    文本输出长度上限
                    <input
                      className={inputClass}
                      type="number"
                      min={256}
                      max={16000}
                      value={envForm.openaiMaxOutputTokens}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          openaiMaxOutputTokens: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="flex items-end gap-3 border border-white/10 bg-black/10 px-4 py-3 text-sm text-zinc-300">
                    <input
                      type="checkbox"
                      checked={envForm.enableRealOpenai}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          enableRealOpenai: event.target.checked,
                        }))
                      }
                    />
                    启用 OpenAI 官方文本通道
                  </label>
                  <label className="col-span-2 text-sm text-zinc-400">
                    文本服务通道
                    <select
                      className={inputClass}
                      value={envForm.textProviderMode}
                      onChange={(event) =>
                        setEnvForm((current) => ({
                          ...current,
                          textProviderMode: event.target.value,
                        }))
                      }
                    >
                      <option value="huimeng_chat">慧梦 GPT-5.5（推荐）</option>
                      <option value="openai_responses">OpenAI 官方</option>
                    </select>
                  </label>
                  <div className="col-span-2 border border-emerald-400/20 bg-emerald-400/7 px-4 py-3 text-sm leading-6 text-emerald-100">
                    文字创作已固定为真实 AI
                    生成。没有配置真实文本服务时，系统会直接提示配置，不会生成占位内容；每次发送前仍会让你确认，防止误扣费。
                  </div>
                </div>
              </details>

              <section className="mt-6 flex items-center justify-between gap-5 border border-white/12 bg-[#151b21]/80 p-5">
                <div className="flex items-start gap-3">
                  <ShieldCheck size={19} className="mt-0.5 text-emerald-300" />
                  <div>
                    <h2 className="text-base font-semibold text-zinc-100">
                      安全原则
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">
                      密钥只写入本机 `.env`，不会显示完整密钥。系统只产出真实 AI
                      结果；每次真实文本、生图或视频请求仍要在任务页确认，防止误扣费。
                    </p>
                  </div>
                </div>
                <GuidePrimaryButton
                  loading={saving}
                  loadingLabel="正在保存设置…"
                  onClick={() => void saveLocalEnv()}
                >
                  保存设置
                </GuidePrimaryButton>
              </section>
            </div>
          }
          aside={
            <div className="space-y-4">
              <DirectorStatusPanel
                title="服务是否能用"
                description="绿色表示已能进入真实生成；灰色表示还没开启或只是备用。所有付费动作仍会在任务页再次确认。"
                items={settingsStageItems}
              />
              <div className="border border-white/10 bg-black/15 p-4 text-sm leading-6 text-zinc-400">
                <p className="font-medium text-zinc-200">大白话规则</p>
                <p className="mt-2">
                  先配文本 AI，再配生图，最后配视频。Key 只写进本机
                  `.env`，页面不会显示完整密钥。
                </p>
              </div>
            </div>
          }
        />
      </div>

      {error ? (
        <p className="mt-4 border border-red-400/25 bg-red-400/7 px-4 py-3 text-sm text-red-200">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="mt-4 border border-emerald-400/25 bg-emerald-400/7 px-4 py-3 text-sm text-emerald-200">
          {message}
        </p>
      ) : null}

      <TechDetails title="可选：即梦账号通道">
        <section className="border border-white/12 bg-[#151b21]/80 p-5">
          <div className="flex items-start justify-between gap-5">
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">
                即梦 CLI 视频通道
              </h2>
              <p className="mt-2 text-sm leading-6 text-zinc-400">
                用你电脑上已登录的 dreamina
                命令提交视频。应用不登录网页、不保存账号密码，也不显示登录凭证。
              </p>
            </div>
            <StatusPill ok={Boolean(jimengCli?.ready)}>
              {jimengCli?.ready ? "已就绪" : "未就绪"}
            </StatusPill>
          </div>
          <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
            <div className="border border-white/10 bg-black/10 p-3">
              <p className="text-zinc-500">CLI</p>
              <p className="mt-1 text-zinc-200">
                {jimengCli?.installed ? "已安装 dreamina" : "未检测到 dreamina"}
              </p>
            </div>
            <div className="border border-white/10 bg-black/10 p-3">
              <p className="text-zinc-500">账号</p>
              <p className="mt-1 text-zinc-200">
                {jimengCli?.logged_in
                  ? jimengCli.account_summary || "已登录"
                  : "未登录或未授权"}
              </p>
            </div>
            <div className="border border-white/10 bg-black/10 p-3">
              <p className="text-zinc-500">积分摘要</p>
              <p className="mt-1 text-zinc-200">
                {jimengCli?.credit_summary || "未读取"}
              </p>
            </div>
            <div className="border border-white/10 bg-black/10 p-3">
              <p className="text-zinc-500">CLI 版本</p>
              <p className="mt-1 break-all text-zinc-200">
                {jimengCli?.cli_version || "未探测"}
              </p>
            </div>
          </div>
          <div className="mt-4 border border-cyan-400/20 bg-cyan-400/5 px-4 py-3 text-sm leading-6 text-zinc-400">
            <p className="font-medium text-cyan-100">即梦 CLI 的适用边界</p>
            <p className="mt-1">
              依赖本机安装、OAuth
              登录和系统钥匙串；模型能力可能晚于即梦网页；参数与参考素材上限以当前
              CLI 版本的帮助输出为准；错误信息和输出解析不如 API
              稳定，不适合跨机器或纯服务器部署。
            </p>
          </div>
          {!jimengCli?.ready ? (
            <p className="mt-4 border border-amber-400/25 bg-amber-400/7 px-4 py-3 text-sm leading-6 text-amber-100">
              {jimengCli?.blocking_reason ||
                jimengCli?.install_hint ||
                "请安装并登录即梦 CLI。"}
            </p>
          ) : null}
        </section>
      </TechDetails>

      {showDevTools ? (
        <details className="mt-6 border border-white/10 bg-black/10">
          <summary className="cursor-pointer px-5 py-4 text-xs text-zinc-500 hover:text-zinc-300">
            开发者调试工具（默认隐藏）
          </summary>
          <div className="border-t border-white/10 p-5 text-sm leading-6 text-zinc-400">
            服务模板、响应映射、试跑证据和用量细节已从主设置页移除。需要排障时再打开开发者工具。
          </div>
        </details>
      ) : null}
    </div>
  );
}

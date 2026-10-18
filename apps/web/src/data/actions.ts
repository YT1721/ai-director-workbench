import {
  Boxes,
  CheckCircle2,
  Clapperboard,
  ClipboardList,
  FastForward,
  Film,
  FolderKanban,
  PencilLine,
  Play,
} from "lucide-react";

export type UcodeAction = {
  code: string;
  label: string;
  command: string;
  description: string;
  icon: typeof Play;
};

export const ucodeActions: UcodeAction[] = [
  {
    code: "start",
    label: "开始",
    command: "V7｜开始｜EP01",
    description: "载入剧本与素材，形成剧情分析和导演方案。",
    icon: Play,
  },
  {
    code: "plan",
    label: "规划",
    command: "V7｜规划｜EP01",
    description: "整理场次、镜头与资产需求，形成制作规划。",
    icon: ClipboardList,
  },
  {
    code: "assets",
    label: "资产",
    command: "V7｜资产｜EP01SC01",
    description: "管理本场人物、服装、场景与正式版本。",
    icon: FolderKanban,
  },
  {
    code: "storyboard",
    label: "故事板",
    command: "V7｜故事板｜EP01SC01｜SH001-SH003",
    description: "生成统一黑白草稿故事板并检查轴线连续。",
    icon: Clapperboard,
  },
  {
    code: "video_package",
    label: "分镜提示词",
    command: "V7｜分镜提示词｜EP01SC01｜SH001",
    description: "汇总单镜头提示词、参考资产和执行资料。",
    icon: Film,
  },
  {
    code: "batch_video",
    label: "批量视频",
    command: "V7｜批量视频｜EP01SC01",
    description: "编排待生成镜头队列，统一检查提交条件。",
    icon: Boxes,
  },
  {
    code: "one_click",
    label: "一键推进",
    command: "V7｜一键｜EP01SC01",
    description: "按确认节点分阶段推进本场制作流程。",
    icon: FastForward,
  },
  {
    code: "check",
    label: "检查",
    command: "V7｜检查｜EP01SC01",
    description: "核查资产、故事板、方向连续性、服务通道与预算。",
    icon: CheckCircle2,
  },
  {
    code: "fix",
    label: "修正",
    command: "V7｜修正｜EP01SC01",
    description: "只修正指定问题，并保留正式版本记录。",
    icon: PencilLine,
  },
];

import {
  Boxes,
  CircleDollarSign,
  ClipboardCheck,
  Film,
  FolderKanban,
  Home,
  Layers3,
  ScrollText,
} from "lucide-react";

export const navigationItems = [
  { key: "home", href: "/", label: "项目总控台", icon: Home },
  { key: "start", href: "/start-plan", label: "开始 / 规划", icon: ScrollText },
  {
    key: "video_package",
    href: "/video-package",
    label: "分镜提示词",
    icon: Film,
  },
  { key: "storyboard", href: "/storyboards", label: "故事板", icon: Layers3 },
  { key: "assets", href: "/assets", label: "资产", icon: FolderKanban },
  { key: "batch_video", href: "/batch-video", label: "批量视频", icon: Boxes },
  { key: "check", href: "/check-fix", label: "流程体检", icon: ClipboardCheck },
  {
    key: "settings",
    href: "/settings",
    label: "成本与设置",
    icon: CircleDollarSign,
  },
];

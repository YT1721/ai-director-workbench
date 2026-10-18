import { describe, expect, it } from "vitest";

import { humanizeCopy } from "./humanCopy";

describe("humanizeCopy", () => {
  it("把上游断线错误改成可操作的中文提示", () => {
    const message = humanizeCopy(
      "文本大脑调用失败：Server disconnected without sending a response.",
    );

    expect(message).toContain("项目和已保存资料没有损坏");
    expect(message).toContain("没有自动重试");
    expect(message).toContain("从剧本识别资产");
    expect(message).not.toContain("Server disconnected");
  });
});

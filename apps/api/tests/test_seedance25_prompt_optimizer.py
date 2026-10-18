from app.services.seedance25_prompt_optimizer import optimize_seedance25_prompt


def test_optimizer_preserves_source_and_compiles_roles_and_sections() -> None:
    source = "儿童扣紧头盔后抬眼看向泥坡，镜头缓慢推进。"
    items = [
        {"number": 2, "content": "结论：建立安全启蒙的情绪转折。可执行清单：不要表现危险动作。"},
        {"number": 8, "content": "结论：镜头稳定缓慢推进。可执行清单：不使用甩镜。"},
        {"number": 10, "content": "结论：儿童扣紧头盔后抬眼。可执行清单：动作克制。"},
        {"number": 12, "content": "结论：清晨森林自然柔光。可执行清单：保持真实。"},
        {"number": 13, "content": "结论：森林环境声与扣带咔哒声。可执行清单：音乐克制。"},
    ]
    bindings = [{
        "token": "@图片1",
        "purpose": "product",
        "label": "头盔产品图",
        "must_preserve": "头盔比例与材质",
        "must_not_transfer": "白底与标注文字",
    }]

    prompt, report = optimize_seedance25_prompt(source, bindings, precision_items=items)

    assert source in prompt
    assert "@图片1：用于产品外观" in prompt
    assert "不得迁移白底与标注文字" in prompt
    assert "主体：儿童扣紧头盔后抬眼" in prompt
    assert "动作 / 事件：建立安全启蒙的情绪转折" in prompt
    assert "运镜 / 切镜：镜头稳定缓慢推进" in prompt
    assert "声音：<音效与环境声：森林环境声与扣带咔哒声>；(音乐：克制)" in prompt
    assert report["mode"] == "deterministic_local_compiler"
    assert report["official_skill_package_installed"] is False
    assert report["source_prompt_sha256"] != report["optimized_prompt_sha256"]


def test_optimizer_can_be_disabled_without_losing_reference_contract() -> None:
    prompt, report = optimize_seedance25_prompt(
        "保持原始镜头文本。",
        [{"token": "@视频1", "purpose": "action", "label": "动作参考"}],
        enabled=False,
    )

    assert "【Seedance 2.5 执行结构】" not in prompt
    assert "@视频1" in prompt
    assert "保持原始镜头文本" in prompt
    assert report["enabled"] is False

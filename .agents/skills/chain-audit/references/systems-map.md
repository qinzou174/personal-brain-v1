# 项目系统全景地图（chain-audit 识别参考）

> 用法：审查前先对照本清单盘点系统；每系统标"生产→存储→消费"落在哪条链；走链时打勾，未打勾=审查缺口。
> 本清单是**活参考**：新增系统时补充，防止审查漏角。

## A 端（实例侧，src/interfaces + domains + systems + core）

| # | 系统 | 职责一句话 | 关键文件 |
|---|---|---|---|
| A1 | 消息接入 | telegram/apk/http 三线进 session.chat | telegram_bot.py / channels/pipeline.py / http_api.py |
| A2 | 缓冲与并发 | 消息合并、生成串行、跨线锁 | message_buffer.py / channels/round.py / suwan_main.py:510 |
| A3 | 提示词系统 | 材料收集→组装→层分离→人格卡 | chat_presenter.py / prompt_orchestrator.py / prompt_layer_separator.py |
| A4 | LLM 客户端 | 调用/重试/超时/空响应/思考开关 | llm_client.py / model_config.py |
| A5 | 工具系统 | schema/执行/回传/C端工具 | tool_category.py / tool_executor.py / tool_callbacks.py / engine_c/* |
| A6 | 欲望系统 | 生成/CDG/欲望板/裁量/映射 | desire_hub.py / contextual_desire_generator.py / desire_board_reviewer.py / desire_intent_mapper.py |
| A7 | 任务系统 | 任务生命周期/舞台/结算/失败 | active_task.py / active_task_executor.py / task_domain.py / stage_engine.py |
| A8 | 情绪系统 | 自报/状态/阻尼/时间线/心境/渲染 | emotion.py / emotion_delta_parser.py / emotion_damping_bus.py / mood.py |
| A9 | 身体系统 | 渴/饿/累曲线与结算 | emotion_domain.py(_update_body) / active_task_executor.py 结算 |
| A10 | 安全系统 | 安全感五维与身体/社交 | security.py / emotion_domain.py(_update_security) |
| A11 | 记忆系统 | 写入门禁/存储/向量/压缩/检索/注入/画像 | memory_domain.py / memory_store.py / memory_engine.py / memory_system_integrator.py / memory_accumulator.py / memory_index_agent.py / memory_selector.py |
| A12 | 反思/认知 | 反思/发散收敛/元认知/做梦/画像融合/叙事 | reflection.py / tick_cognitive_agent.py / pattern_distiller.py / tick_narrative_composer.py / metacognition.py |
| A13 | 人格系统 | 人设/演变/灵魂/信念/立场/慢变量 | persona_profile.py / evolution_recorder.py / belief.py / stance / slowvar |
| A14 | 关系系统 | 关系值/社交评估/线程关系 | relationship.py / social_appraisal.py / scene_encounter.py |
| A15 | 媒体系统 | 衣柜/照片/语音/表情包 | wardrobe.py / media_api.py / media_client_impl.py / engine_c/meme |
| A16 | 快照/持久化 | 快照保存/重启恢复/状态落盘 | state_persistence.py / tick_orchestrator.py 恢复 |
| A17 | 后台调度 | tick 循环/定时闸门/孤儿清理 | shared_runtime.py / tick_stage_runner.py / tick_phase_engine.py(废弃) |
| A18 | 行为账本 | 世界事件/任务/工具→账本→反思消费 | tick_orchestrator.py / memory_read_domain.py(action_ledger) |
| A19 | 承诺/补答 | 承诺账本/W3 补答 | chat_commitment.py / channels/followup_store.py / pipeline.py |
| A20 | 主动消息 | want_to_share/定时提醒 | proactive_messenger.py / systems/initiative |
| A21 | 意图执行 | 意图→动作/工具链执行 | intent_executor.py / active_task_executor.py |

## B 端（世界侧，src/engine_b）

| # | 系统 | 职责一句话 | 关键文件 |
|---|---|---|---|
| B1 | 世界状态 | 时间/天气/地点/实体/在线 | world_state.py / world.py |
| B2 | 场景推理 | 路径/地点/天气描写（3h） | scene_reasoning_engine.py / scheduler.py |
| B3 | 事件系统 | 导演事件/mutate/事件账本 | director.py / world.py(mutate) / event_policy.py |
| B4 | 经济系统 | 钱包/商品/购买/定价 | economy_service.py / content_registry.py / world.py(_init_goods) |
| B5 | 旅程系统 | journey/共享旅程/共同经历 | world.py(1073-1172) / scheduler.py |
| B6 | 社交系统 | 对话池/社交请求/私信线程 | world.py(对话/thread) / prompt_service.py |
| B7 | 实体登记 | register/位置/在场投影 | write_apis.py / world.py(458) / prompt_service.py |

## C 端（外部能力，src/engine_c + media）

| # | 系统 | 职责一句话 | 关键文件 |
|---|---|---|---|
| C1 | 天气 | 实时天气/叙述 | weather_engine.py / weather_client_impl.py / mcp_weather_server.py |
| C2 | B站/视频 | 视频搜索/播放 | bilibili_api.py / bilibili_client_impl.py |
| C3 | 表情包 | 搜索/发送 | meme_api.py / meme_client_impl.py |
| C4 | 追踪 | 定位/追踪 | tracking_api.py / tracking_client_impl.py |
| C5 | 媒体渲染 | 生图/语音/衣柜图 | media_api.py / media_voice_assembler.py / media_prompt_assembler.py |

## 覆盖核对方法

审查走完全部绳子后，逐系统打勾：A1-A21 + B1-B7 + C1-C5 = 33 个系统。未打勾的 → 单独从它的"生产者入口"补走一条链到"消费者尽头"，再回来继续。缺系统 = 地图不完整 = 项目可能有没人审的角落。

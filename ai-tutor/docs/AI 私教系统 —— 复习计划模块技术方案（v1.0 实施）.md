# AI 私教系统 —— 复习计划模块技术方案（v1.0 实施）

基于《复习计划模块产品设计文档（v1.0 定稿）》的落地技术方案
版本：1.0 | 日期：2026-09-09 | 状态：已确认（4 项决策点）

---

## 0. 决策记录（用户已确认）

| # | 决策点 | 结论 |
|---|--------|------|
| D1 | 毕业制切换（B1） | **全部改为新判定**（连胜制）。现有数据均为测试数据，不做历史保留，无回填 |
| D2 | 验证失败重新入池（B2） | **按文档执行**：`next_review = now()`，验证失败的词立刻回到全局待复习池 |
| D3 | 费曼评分限流（B3） | **每组最多 AI 评分 5 题**（verification_set 中随机任选 5 个），其余按 binary（记得/不记得）快速验证 |
| D4 | Redis 会话快照（B4） | **接受简化**：存前端内存结构，不做后端一致性校验，恢复时以 pending 接口校准 |

---

## 1. 现状与差距

### 已满足（无需改动）
- SM-2 三分支（quality 5/3/0）、`need_session_retry` 驱动
- main_queue / retry_queue（前端 verifyQueue）内存双队列
- 重试/组后验证纯前端逻辑（放行零后端交互）
- 手动标熟 `/master`、批次空态、`limit=20` 分批
- 3 级语义化按钮 + 算法后果副文案、进度条 + 点阵、🔁 重试标记、作答后展开答案解析

### 差距（本次实施范围）
| 编号 | 文档要求 | 现状 | 方案 |
|---|---|---|---|
| G1 | 毕业 = 连续 3 次正式 mastered（§11.3/§13） | `mastery_score >= 90` 即毕业 | 改连胜制 |
| G2 | 验证失败 → 重新加入全局待复习池（§10.3） | `verification-failed` 不重置 next_review | next_review = now() |
| G3 | 组后验证 = 费曼解释 + AI 评分（§10.3） | 前端"记得/不记得"替身，无评分接口 | 新增 /feynman-verify + 前端费曼 UI |
| G4 | 组完成庆祝页 + 本组统计 + TOP3（§10.2） | done 页仅一句文案 | 前端内存聚合 + 庆祝页 |
| G5 | 中途退出保存/恢复（§12.1） | 会话纯内存，刷新即丢 | Redis 快照 ± 5min 自动暂停 |
| G6 | 极速点击 <500ms 无效化、防抖 1s（§11.1） | 无拦截无防抖 | 前后端双拦截 + 防抖 |
| G7 | source_type=wrong_book/manual + tag_filter（§11.3） | pending 仅有 limit | 加过滤参数 |
| G8 | 基础埋点（§12.1） | 无 | review_batch_stats 表 + /batch-complete |

**明确不纳入**：v1.1 全项（多轮递进/个性化间隔/连胜跳级/复习债仪表盘）、v1.2 全项（推送/专项攻克/周报/A/B）、刷分检测、网络断开 localStorage 回放、Redis 宕机降级、乐观锁。

---

## 2. 后端方案

### 2.1 毕业制改连胜（G1，决策 D1）

`review-agent/app/tools/spaced_repetition.py`：
- `calculate_next_review()` 中 `status = "mastered" if mastery_score >= 90 else "active"` 改为 `status = "mastered" if correct_streak >= 3 else "active"`
- `mastery_score` 保留为展示维度，与毕业解耦
- 联动修正 `schedule_manager.py` `submit_verification_failed()` 中残留的 `>= 90` 判定（验证失败是降级操作，绝不置 mastered）

### 2.2 verification-failed 重新入池（G2，决策 D2）

`review-agent/app/tools/schedule_manager.py` `submit_verification_failed()`：
- 保留：ease_factor -0.05、mastery_score -3、ReviewLog 落库
- 新增：`schedule.next_review = datetime.utcnow()`（立刻回到全局池）
- 修正：status 保持 active（不做 >=90 判定）、is_mastered 保持 0
- 同步更新 gateway `review.py` 路由注释（不再"不重置间隔"）

### 2.3 费曼 AI 评分接口（G3，决策 D3）

**新文件 `gateway/app/services/llm_client.py`**：从 `feynman.py` 抽取 SiliconFlow 公共 client
- `chat_json(system_prompt, user_content, max_tokens, temperature) -> dict`：httpx 直调 + JSON 正则抽取 + 缺省值回退
- API key 改为环境变量 `SILICONFLOW_API_KEY`（feynman.py 硬编码同步移除，该 key 已由 compose 注入）
- 模型 `deepseek-ai/DeepSeek-V3` 不变

**`gateway/app/api/review.py` 新增 `POST /api/review/feynman-verify`**：
- 请求：`{schedule_id, chunk_id?, explanation}`（topic/answer 从 ReviewSchedule 读取，不依赖 chunk join；feynman/manual 来源 chunk_id 为 NULL 也可用）
- 评分基准：`schedule.topic` + `schedule.answer`（参考答案）
- 响应：`{score, strengths[], weaknesses[], suggestions[]}`（score 0-100）
- 落库：写一条 `VerificationLog`（verification_type=feynman，ai_score，passed = score>=80）
- 通过/失败**不**在此接口改 memory 状态；`<80` 由前端继续调 `/verification-failed`（防双写）

### 2.4 Redis 会话快照（G5，决策 D4）

`redis[hiredis]` 已在顶层 pyproject，compose 已注入 `REDIS_URL`——零新依赖，gateway 直接 `redis.asyncio.from_url`。

`gateway/app/api/review.py` 新增（复用 `redis://redis:6379/0`）：
- `POST /api/review/session`：保存快照 `{batch_id, batch_index, main_queue, retry_queue, verify_queue, current_card, stats}`，key=`review:session:{user_id}`，TTL 24h
- `GET /api/review/session`：读取快照；无则 404
- `DELETE /api/review/session`：清除（正常完成/主动退出/用户拒绝恢复时调用）
- 快照存前端结构原样，不做校验（D4）

### 2.5 pending 过滤（G7）

`GET /api/review/pending` 新增可选参数：
- `source_type=daily|wrong_book|manual`：daily=默认全量；wrong_book = `source='quiz' AND reason='wrong'`（复用 quiz.py:276 错题入池标记）；manual = `source='manual'`
- `tag_filter`：JOIN chunks 按 `tags` JSON 过滤，仅对 `chunk_id` 非空记录生效
- 前端复习页顶部下拉选择池来源，默认 daily

### 2.6 基础埋点（G8）

- 迁移 006：`review_batch_stats` 表（user_id, batch_id, total_count, mastered_count, retry_count, duration_sec, avg_response_ms, created_at）
- `POST /api/review/batch-complete`：组完成时前端上报一次，本期只写不读

### 2.7 极速点击后端兜底（G6）

`POST /review/normal` 校验 `response_time_ms < 500` → 400 `{"detail": "请仔细思考后再作答"}`（防前端绕过）。

---

## 3. 前端方案（web-app）

### 3.1 api.ts（F6）
- 替换死代码 `sessionApi`（指向不存在的路由）为：`saveSession/loadSession/clearSession`、`feynmanVerify`、`batchComplete`
- `getPending` 增加 source_type/tag_filter 参数
- 同步扩展 `web-app/src/types/index.ts`（FeynmanVerifyResponse、SessionSnapshot、BatchCompletePayload）

### 3.2 统计聚合（F4 数据源）
会话内 `stats` state：batchStartTime、每题 responseTimeMs、每题重试次数 map、每题最终结果（mastered/降级）。纯内存。

### 3.3 组完成庆祝页（G4）
done 阶段重写为：
- 🎉 第 N 组完成、本组掌握 n/m（首次 mastered 数/组总数）、完美组零重试 ✨
- 三统计卡：总用时（mm分ss秒）、平均反应、重试次数
- 待攻克难点 TOP 3：按「重试次数 > 不认识次数 > 平均反应」排序取前 3
- [继续下一组 ▶] → 重新 getPending()，batch_index+1；池空 → "今日复习真正完成" 终态
- [暂停退出] → navigate(-1)

### 3.4 组后验证改费曼（G3，决策 D3）
verifying 阶段流程（决策 D3 限流版）：
1. 进入验证 → verifyQueue 中**随机选 5 个**标记为「费曼题」，其余为「快速题」
2. 每张卡：先「回想」→ 展开答案解析（不变）
3. **费曼题**：textarea 输入解释 → 字数统计（<20 字禁用提交+提示）→ [提交供 AI 评分] → 评分结果卡（分数 + ✅/⚠️/建议 + [确定]/[重新解释]）→ `>=80` 出队（零后端）；`<80` 调 `/verification-failed` 后出队（回到全局池，D2）
4. **快速题**：保持现有「记得 ✓ / 不记得 ✗」binary 验证（不调 LLM）
5. 保留 🔁 重试 badge

### 3.5 会话恢复 + 5min 无操作（G5，决策 D4）
- 进入页面：`GET /session` 有快照 → 弹「恢复上次未完成复习？」确认恢复 / 拒绝清除
- 5 分钟无操作定时器：自动 `POST /session` 保存 + 暂停遮罩「已暂停，点击继续」
- `beforeunload` 触发保存；正常完成/退出时 `DELETE /session`

### 3.6 极速点击与防抖（G6）
- 作答拦截：`Date.now() - cardShowTime < 500ms` → 不提交不推进，提示「请仔细思考后再作答」
- 提交按钮 1s 防抖（submitting 态升为 cooldown）
- 后端 400 双保险（2.7）

### 3.7 池来源入口（G7）
复习页顶部下拉：「每日复习（默认）/ 错题本 / 手动添加」，切换后重新拉取。

---

## 4. 迁移与配置

| 项 | 内容 |
|---|---|
| 迁移 006 | `review_batch_stats` 表（含索引）+ 直接 psql 应用到运行中 DB（沿用 003/004/005 手工迁移体系），迁移文件落 `migrations/versions/` |
| 环境变量 | `SILICONFLOW_API_KEY`：feynman.py 硬编码 → env（.env 已有，compose 已注入，无需改 compose） |
| 数据 | 全部测试数据，毕业制切换不回填（D1） |

---

## 5. 实施顺序与验证门禁

1. 后端：B1 → B2 → B3（llm_client 抽取 + feynman-verify）→ B4（session）→ B5（pending 过滤）→ B6（迁移 006 + batch-complete）→ 2.7（500ms 拒答）
2. 前端：types → api.ts → 3.6 拦截 → 3.4 费曼验证 → 3.3 庆祝页 → 3.5 会话恢复 → 3.7 池来源
3. 门禁：
   - tsc --noEmit 通过
   - 重建 gateway/web-app 容器，启动无错
   - API 冒烟：feynman-verify（真 key，期望 JSON 含 score）、session save/restore/clear 往返、pending?source_type/tag_filter、batch-complete、500ms 拒答 400
   - E2E（playwright-core + Chrome）：3 卡组 → 认识/模糊/不认识 → 组后验证费曼（1 题）≥80 通过 + <80 降级 → 庆祝页统计 → 继续下一组/空态；console 零错误
4. 收尾：清理 temp、git status 汇报

---

## 6. 风险

| 风险 | 缓解 |
|---|---|
| LLM 评分延迟/失败 | 评分接口 60s 超时；LLM 异常返回 502，前端允许「跳过此题按快速题处理」 |
| 费曼题随机 5 个可能漏掉真正难的 | 收益 > 成本，v1.1 可改为按重试次数优先 |
| Redis 快照与 DB 不一致（D4 接受） | 恢复后 pending 接口校准；TTL 24h 自过期 |
| 验证失败词当天重入池（D2 接受） | 产品文档明文行为，前端提示「已回到待复习池」 |
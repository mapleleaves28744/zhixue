# 智学工坊 IP 资产 UI 集成规范

本文用于约束 `frontend/public/stickers/*` 与 `frontend/public/brand/*` 在 Stitch 学生端中的使用方式，避免 IP 图只作为装饰堆叠，确保它服务于学习状态表达与演示解释。

## 1. 使用原则

1. IP 贴纸优先用于空状态、思考中、生成成功、提醒、搜索中、错误不确定等状态。
2. 不用贴纸冒充真实数据；没有数据时必须明确说明“暂无/待生成/需完成学习行为”。
3. 空状态默认使用 `ZhixueUI.emptyState` 或 `ZhixueUI.renderEmptyState`，不要在页面里继续散落 Material Icon + 文案的自定义空状态。
4. 侧栏、小列表、历史记录等紧凑区域使用 `compact: true`，避免贴纸撑破布局。
5. 品牌大图只用于品牌首页或氛围装饰；功能卡片优先使用本地化后的真实视觉资产。

## 2. 页面 Mascot 映射

| 页面 | 主 mascot | 定位 | 默认空状态 |
|---|---|---|---|
| `/` / `/home` | `lulu` | 学习总览、提醒与任务节奏 | `reminder` |
| `/courses` | `zhizhi` | 课程创建与资料入口 | `greeting` |
| `/knowledge` | `zhizhi` | Wiki、资料解析、知识检索 | `searching` / `empty` |
| `/assistant` | `zhizhi` | AI Tutor、资源生成、引用整理 | `thinking` |
| `/practice` | `diandian` | 练习、错题、诊断反馈 | `empty` / `reminder` / `unsure` |
| `/dashboard` | `lulu` | 学习状态概览与推荐提醒 | `reminder` |
| `/path-profile` | `lulu` | 学生画像、长期记忆、自进化策略、学习路径 | `empty` / `thinking` / `searching` |

## 3. 贴纸场景

| scene | 文件 | 推荐用途 |
|---|---|---|
| `greeting` | `01_happy_greeting.png` | 新用户、创建第一项内容 |
| `thinking` | `02_thinking.png` | AI 正在生成、策略分析待触发 |
| `searching` | `08_searching.png` | Wiki 检索、路径规划、资料查找 |
| `updated` | `09_updated.png` | 保存、更新、同步完成 |
| `reminder` | `07_reminder.png` | 复习提醒、历史记录为空、下一步建议 |
| `empty` | `05_sleepy_idle.png` | 暂无数据、等待学习行为产生 |
| `unsure` | `11_unsure.png` | 加载失败、诊断不足、需要核对 |
| `success` | `12_completed.png` | 练习完成、策略生效、任务完成 |

## 4. 实现约定

大面板空状态：

```js
window.ZhixueUI.renderEmptyState(container, {
  mascot: "zhizhi",
  scene: "searching",
  title: "还没有 Wiki 页面",
  description: "上传资料并生成 Wiki 后，这里会显示知识点页面。",
});
```

模板字符串场景：

```js
window.ZhixueUI.emptyState({
  mascot: "diandian",
  scene: "reminder",
  title: "暂无历史诊断",
  description: "完成练习后运行诊断，系统会保存报告。",
  compact: true,
})?.outerHTML;
```

## 5. 当前接入范围

已接入或保留：

1. `/knowledge`：Wiki 空列表、资料空列表继续使用 `ZhixueUI.renderEmptyState`。
2. `/courses`：无真实课程时使用知知创建引导。
3. `/assistant`：资源生成历史为空时使用知知 compact 状态。
4. `/practice`：无题、错题为空、诊断为空、加载失败统一使用点点状态。
5. `/home`：最近活动为空使用露露提醒状态。
6. `/path-profile`：长期记忆、自进化策略、学习路径为空使用露露状态。

后续 Sprint 可继续把细粒度的“暂无摘要/暂无标签/暂无薄弱点”这类行内文案保留为文本，不强制贴纸化，避免页面过度视觉化。

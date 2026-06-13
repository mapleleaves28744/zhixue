# Agent Skills（后端运行时）

互动课件生成使用 vendored 的 [lewislulu/html-ppt-skill](https://github.com/lewislulu/html-ppt-skill)（MIT）。

更新 skill：

```bash
rm -rf backend/app/skills/html-ppt-skill
git clone --depth 1 https://github.com/lewislulu/html-ppt-skill.git backend/app/skills/html-ppt-skill
```

**智学工坊补丁**（重新 clone 后需手动恢复）：`assets/runtime.js` 已增加滚轮翻页与 ↑↓ 方向键，见 git diff。

加载入口：`app/skills/skill_loader.py`  
业务入口：`app/services/html_ppt_courseware_service.py`

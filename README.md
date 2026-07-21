# training-exam-question-generator

纵腾集团新人培训考试题库生成 Skill — 七步出题流程

## 结构

```
.
├── SKILL.md                          # 主流程文档（七步出题法）
├── references/
│   ├── question_templates.md        # 试题模板规范
│   └── pitfalls_and_checks.md       # 踩坑清单与校验要点
└── scripts/
│   └── consistency_check.py         # 一致性自动校验脚本
```

## 快速开始

1. 阅读主流程文档：
   - [七步出题流程](SKILL.md)
2. 查看模板与注意事项：
   - [试题模板](references/question_templates.md)
   - [踩坑清单](references/pitfalls_and_checks.md)
3. 出题后运行校验脚本检查一致性：
   ```bash
   python3 scripts/consistency_check.py <题目文件.txt>
   ```

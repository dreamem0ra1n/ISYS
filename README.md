# ISYS

`@dreamem0ra1n`自建的`zju-is`课程资源站

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `content/` | 课程、杂项等页面 |
| `src/components/`、`src/styles/` | ISYS 自己的导航组件和样式 |
| `quartz/` | Quartz 构建引擎，站点定制尽量放在 `src/` |
| `scripts/` | 课程数据转换和构建辅助脚本 |
| `data/` | 本地课程 JSON，默认不纳入 Git |
| `quartz.ts`、`quartz.config.yaml` | Quartz 要求位于根目录的入口与站点配置 |

`node_modules/`、`public/`、`.quartz/` 和 `.cache/` 都是可重新生成的产物，已加入 `.gitignore`。根目录的 `package.json`、`package-lock.json`、`tsconfig.json`、`.node-version` 和 `.npmrc` 分别用于依赖、TypeScript 和 Node 环境。

## 本地预览

安装 Node.js 依赖并启动 Quartz：

```bash
npm install
npm run quartz -- plugin install --from-config
npm run serve
```

默认预览地址为 `http://localhost:8080`。

`npm run build` 和 `npm run serve` 会在启动前更新首页的页面数、汉字数、历史贡献者及更新记录。历史贡献者来自 Git 提交作者（排除 `root` 和机器人）；若 Git 作者名与 GitHub 用户名不同，在 `scripts/contributors.json` 中补充对应关系。生成名单需要完整的 Git 历史。

## 从 JSON 构建课程页面

构建脚本会读取 `data` 目录中的 JSON，根据
[`content/template.md`](content/template.md) 生成课程 Markdown。Quartz 会按
`content/` 的目录结构生成页面；侧栏的“25级前”和“26级”视图会对同一课程页面采用不同分类。

课程视图由 [`src/components/CourseViews.tsx`](src/components/CourseViews.tsx) 维护。新增课程时，先按“25级前”分类建立页面；若 26 级分类不同，在该文件的 `changes` 中记录页面 slug 与新分类。尚无页面的新课程列在 `missingCourses`。站点会记住读者选择的视图，课程页面的分类标签也随之切换。课程内容中的学分、推荐学期等历史信息仍需按实际适用年级注明。

完整的数据示例见
[`scripts/course_data.example.json`](scripts/course_data.example.json)。可以先创建自己的数据文件：

```bash
mkdir -p data
cp scripts/course_data.example.json data/新课程.json
```

最小 JSON 只需要 `title`：

```json
{
  "title": "新课程"
}
```

常用字段示例：

```json
{
  "title": "新课程",
  "en_title": "New Course",
  "category": "专业必修",
  "credits": 2.5,
  "location": "玉泉",
  "course_number": "CS0001M",
  "recommended_semester": "大三春夏",
  "description": "这里填写课程简介。",
  "teachers": [
    {
      "term": "26春夏",
      "items": ["教师甲", "教师乙"]
    }
  ],
  "textbooks": ["教材名称"]
}
```

除 `title` 外，其余字段都可以省略。课程简介等文本字段可以直接包含 Markdown。`teachers` 必须是学期对象数组，每个对象通过
`term` 指定学期，通过 `items` 列出该学期的任课教师。成绩构成、多级列表、外链和回忆卷的
写法请参考完整示例。

资源使用分组对象，其中 `links` 是外链索引，`exams` 是可选的分学期回忆卷，其他资源可以
放入 `sections`：

```json
{
  "resources": {
    "links": [
      {
        "title": "课程网站",
        "url": "https://example.com",
        "description": "课程资料"
      }
    ],
    "exams": [
      {
        "term": "26春夏",
        "items": [
          {
            "title": "期末回忆卷",
            "url": "https://example.com/exam"
          }
        ]
      }
    ],
    "sections": [
      {
        "title": "实验文档",
        "items": [
          {
            "title": "实验网站",
            "url": "https://example.com/lab"
          }
        ]
      }
    ]
  }
}
```

没有回忆卷时可以直接省略 `exams`。

课程头部的重要提示放在 `notes` 中。字符串会生成普通 `note`，需要保留警告类型时使用对象：

```json
{
  "notes": [
    "普通提示",
    {
      "type": "warning",
      "title": "需要特别注意的重要信息"
    }
  ]
}
```

支持的 `category` ：`专业基础`、`专业必修`、`专业进阶`、`实践教学`、`专业选修-应用基础`、`专业选修-实践拓展`

### 校验与构建

校验 `data/**/*.json` 并预览目标页面路径，不写入文件：

```bash
python scripts/build_course_md.py --check
```

只构建一个 JSON（如果省略该参数则构建所有 JSON）：

```bash
python scripts/build_course_md.py data/新课程.json
```

如果目标 Markdown 已存在，脚本会拒绝覆盖。确认需要重新生成时使用：

```bash
python scripts/build_course_md.py data/新课程.json --force
```

只在终端预览生成的 Markdown，不写入页面：

```bash
python scripts/build_course_md.py data/新课程.json --stdout
```

每个 JSON 文件只能包含一个课程对象。一门课程对应一个 JSON 文件和一个生成的 Markdown 页面；
需要构建多门课程时，请在 `data` 目录中分别创建多个 JSON 文件。

构建完成后直接运行 `npm run serve`，新课程就会出现在站点导航中。

### 从现有 Markdown 导出 JSON

需要把已有课程页面反向导出到 `data` 时，可以先预演：

```bash
python scripts/export_course_json.py --check
```

确认后生成：

```bash
python scripts/export_course_json.py
```

脚本只处理带有 `course-tags` 的课程页面，并保持与 `content` 相同的目录层级。一个 Markdown
对应一个 JSON；`content/Welcome to ISYS.md` 等非课程页面会被忽略。目标 JSON 已存在时，
需要使用 `--force` 才会重新导出：

```bash
python scripts/export_course_json.py --force
```

## 删除课程页面

删除脚本会同时删除 Quartz `content/` 中的课程 Markdown 页面。

建议先检查：

```bash
python scripts/delete_course_md.py content/新课程.md --check
```

确认后删除课程 Markdown。课程目录会在下次构建时自动更新：

```bash
python scripts/delete_course_md.py content/新课程.md
```

页面已经不存在、需要忽略缺失错误时使用：

```bash
python scripts/delete_course_md.py content/新课程.md --missing-ok
```

构建命令支持传入多个 JSON 文件，删除命令支持传入多个 Markdown 路径。其他选项可以通过
`--help` 查看：

```bash
python scripts/build_course_md.py --help
python scripts/delete_course_md.py --help
```

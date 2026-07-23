# ISYS

`@dreamem0ra1n`自建的`zju-is`课程资源站

## 本地预览

安装依赖并启动 MkDocs：

```bash
pip install -r requirements.txt
mkdocs serve
```

默认预览地址为 <http://127.0.0.1:8000>。

## 从 JSON 构建课程页面

构建脚本会读取 `data` 目录中的 JSON，根据
[`docs/杂项/template.md`](docs/杂项/template.md) 生成课程 Markdown，并自动把页面加入
`mkdocs.yml` 的对应导航层级。

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
  "nav_title": "新课程",
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

除 `title` 外，其余字段都可以省略。`nav_title` 用于自定义 `mkdocs.yml` 中显示的名称；
课程简介等文本字段可以直接包含 Markdown。`teachers` 必须是学期对象数组，每个对象通过
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

支持的 `category` 及默认输出目录：

| `category` | 输出目录 |
| --- | --- |
| `专业基础` | `docs/专业基础/` |
| `专业必修` | `docs/专业必修/` |
| `专业进阶` | `docs/专业进阶/` |
| `实践教学` | `docs/实践教学/` |
| `专业选修-应用基础` | `docs/专业选修/应用基础类/` |
| `专业选修-实践拓展` | `docs/专业选修/实践拓展类/` |

### 校验与构建

校验 `data/**/*.json` 并预览目标页面和导航变化，不写入文件：

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

只在终端预览生成的 Markdown，不写页面或导航：

```bash
python scripts/build_course_md.py data/新课程.json --stdout
```

每个 JSON 文件只能包含一个课程对象。一门课程对应一个 JSON 文件和一个生成的 Markdown 页面；
需要构建多门课程时，请在 `data` 目录中分别创建多个 JSON 文件。

构建完成后直接运行 `mkdocs serve`，新课程就会出现在站点导航中。

### 从现有 Markdown 导出 JSON

需要把已有课程页面反向导出到 `data` 时，可以先预演：

```bash
python scripts/export_course_json.py --check
```

确认后生成：

```bash
python scripts/export_course_json.py
```

脚本只处理带有 `course-tags` 的课程页面，并保持与 `docs` 相同的目录层级。一个 Markdown
对应一个 JSON；`docs/index.md`、`docs/杂项/` 等非课程页面会被忽略。目标 JSON 已存在时，
需要使用 `--force` 才会重新导出：

```bash
python scripts/export_course_json.py --force
```

## 删除课程页面

删除脚本会同时删除课程 Markdown 和 `mkdocs.yml` 中对应的导航项；如果某个导航分组已经没有课程，
也会清理该空分组。

建议先检查：

```bash
python scripts/delete_course_md.py docs/专业必修/新课程.md --check
```

确认后删除课程 Markdown 和对应导航项：

```bash
python scripts/delete_course_md.py docs/专业必修/新课程.md
```

页面已经不存在、只需要清理残留导航时使用：

```bash
python scripts/delete_course_md.py docs/专业必修/新课程.md --missing-ok
```

构建命令支持传入多个 JSON 文件，删除命令支持传入多个 Markdown 路径。其他选项可以通过
`--help` 查看：

```bash
python scripts/build_course_md.py --help
python scripts/delete_course_md.py --help
```

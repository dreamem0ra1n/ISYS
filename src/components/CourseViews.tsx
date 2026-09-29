import {
  QuartzComponent,
  QuartzComponentProps,
} from "../../quartz/components/types";
import { FullSlug, resolveRelative } from "../../quartz/util/path";

const categories = [
  "专业基础",
  "专业必修",
  "专业选修/应用基础类",
  "专业选修/实践拓展类",
  "实践教学",
  "专业进阶",
] as const;

type Category = (typeof categories)[number];

const originalCategories: Record<string, Category> = {
  数据结构基础: "专业基础",
  面向对象程序设计: "专业基础",
  高级数据结构与算法分析: "专业必修",
  信息安全原理与数学基础: "专业必修",
  数据安全与密码学基础: "专业必修",
  无线与物联网安全基础: "专业必修",
  系统安全原理与实践: "专业必修",
  网络安全原理与实践: "专业必修",
  计算机系统Ⅰ: "专业必修",
  计算机系统Ⅱ: "专业必修",
  计算机系统Ⅲ: "专业必修",
  计算机网络: "专业必修",
  软件安全原理和实践: "专业必修",
  隐私计算与数据合规: "专业必修",
  人工智能安全: "专业进阶",
  密码学进阶: "专业进阶",
  深度合成技术与电子取证: "专业进阶",
  硬件安全基础: "专业进阶",
  编程语言原理: "专业进阶",
  编译原理: "专业进阶",
  软件保护技术: "专业进阶",
  专题研讨: "专业选修/实践拓展类",
  区块链安全与数字货币原理: "专业选修/实践拓展类",
  社交网络安全与隐私: "专业选修/实践拓展类",
  职业发展规划讲座: "专业选修/实践拓展类",
  计算机科学思想史: "专业选修/实践拓展类",
  计算理论: "专业选修/实践拓展类",
  量子计算理论基础与软件系统: "专业选修/实践拓展类",
  信息安全管理: "专业选修/应用基础类",
  多媒体安全: "专业选修/应用基础类",
  数据库系统: "专业选修/应用基础类",
  汇编语言程序设计与调试: "专业选修/应用基础类",
  网络空间安全导论: "专业选修/应用基础类",
  面向信息安全的信号处理: "专业选修/应用基础类",
  信息安全产业实践: "实践教学",
  "信息安全课程综合实践(CTF101)": "实践教学",
};

const changes: Record<string, Category | null> = {
  网络空间安全导论: "专业必修",
  区块链安全与数字货币原理: null,
  人工智能安全: "专业必修",
  计算机网络: "专业选修/应用基础类",
  软件安全原理和实践: "专业选修/应用基础类",
  系统安全原理与实践: "专业选修/应用基础类",
  网络安全原理与实践: "专业进阶",
};

const removedIn26 = new Set([
  "数据结构基础",
  "高级数据结构与算法分析",
  "信息安全管理",
  "编程语言原理",
]);

const newCoursesIn26: Record<string, Category> = {
  数据结构与算法: "专业基础",
  区块链与数字货币: "专业必修",
  编译系统实践: "专业进阶",
};

const sitePages = [
  "index",
  "26级培养方案概览",
  "友链",
  "工作流和信息渠道",
  "更新记录和计划",
] as const;

function originalCategory(slug: string): Category | undefined {
  return Object.entries(originalCategories).find(
    ([name]) => name.toLowerCase() === slug.toLowerCase(),
  )?.[1];
}

function currentCategory(slug: string): Category | null | undefined {
  if (removedIn26.has(slug)) return null;
  return Object.hasOwn(newCoursesIn26, slug)
    ? newCoursesIn26[slug]
    : Object.hasOwn(changes, slug)
      ? changes[slug]
      : originalCategory(slug);
}

function categoryLabel(category: Category): string {
  return category.replace("/", " · ");
}

const CourseViews: QuartzComponent = ({
  allFiles,
  fileData,
}: QuartzComponentProps) => {
  const currentSlug = (fileData.slug ?? "index") as FullSlug;
  const courses = allFiles.filter(
    (file) =>
      file.slug &&
      (originalCategory(file.slug) || Object.hasOwn(newCoursesIn26, file.slug)),
  );
  const currentOriginal = originalCategory(currentSlug);
  const currentNew = currentCategory(currentSlug);

  const catalog = (view: "25" | "26") => (
    <div class="course-view-panel" data-view={view}>
      {view === "26" && (
        <p class="course-view-note">
          分类依据{" "}
          <a
            href={resolveRelative(currentSlug, "26级培养方案概览" as FullSlug)}
          >
            26级培养方案概览
          </a>
        </p>
      )}
      {categories.map((category) => {
        const entries = courses
          .filter((file) =>
            view === "25"
              ? originalCategory(file.slug!) === category
              : currentCategory(file.slug!) === category,
          )
          .sort((first, second) =>
            String(first.frontmatter?.title).localeCompare(
              String(second.frontmatter?.title),
              "zh-CN",
            ),
          );
        return (
          <details class="course-view-group" open>
            <summary>{categoryLabel(category)}</summary>
            <ul>
              {entries.map((file) => {
                return (
                  <li>
                    <a
                      href={resolveRelative(currentSlug, file.slug as FullSlug)}
                      aria-current={
                        file.slug === currentSlug ? "page" : undefined
                      }
                    >
                      {file.frontmatter?.title ?? file.slug?.split("/").at(-1)}
                    </a>
                  </li>
                );
              })}
            </ul>
          </details>
        );
      })}
    </div>
  );

  const siteNavigation = (
    <details class="course-view-group course-view-site" open>
      <summary>站点信息</summary>
      <ul>
        {allFiles
          .filter((file) =>
            sitePages.includes(file.slug as (typeof sitePages)[number]),
          )
          .sort(
            (first, second) =>
              sitePages.indexOf(first.slug as (typeof sitePages)[number]) -
              sitePages.indexOf(second.slug as (typeof sitePages)[number]),
          )
          .map((file) => (
            <li>
              <a href={resolveRelative(currentSlug, file.slug as FullSlug)}>
                {file.slug === "index"
                  ? "Welcome to ISYS"
                  : (file.frontmatter?.title ?? file.slug)}
              </a>
            </li>
          ))}
      </ul>
    </details>
  );

  const navigation = () => (
    <>
      <div class="course-view-switch" role="group" aria-label="课程分类视图">
        <button type="button" data-switch-view="25" aria-pressed="true">
          25级前
        </button>
        <button type="button" data-switch-view="26" aria-pressed="false">
          26级
        </button>
      </div>
      {siteNavigation}
      {catalog("25")}
      {catalog("26")}
    </>
  );

  return (
    <div
      class="course-views"
      data-category-25={currentOriginal ?? ""}
      data-category-26={currentNew === null ? "仅25级前" : (currentNew ?? "")}
    >
      <nav class="course-view-desktop" aria-label="课程目录">
        <h2>课程目录</h2>
        {navigation()}
      </nav>
      <details class="course-view-mobile">
        <summary>课程目录</summary>
        <nav aria-label="课程目录">{navigation()}</nav>
      </details>
    </div>
  );
};

CourseViews.beforeDOMLoaded = `
  try {
    if (localStorage.getItem("isys-course-view") === "26") {
      document.documentElement.dataset.courseView = "26"
    }
  } catch {}
`;

CourseViews.afterDOMLoaded = `
  function syncCourseView() {
    const view = document.documentElement.dataset.courseView === "26" ? "26" : "25"
    document.querySelectorAll("[data-switch-view]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.switchView === view))
      button.onclick = () => {
        document.documentElement.dataset.courseView = button.dataset.switchView
        try { localStorage.setItem("isys-course-view", button.dataset.switchView) } catch {}
        syncCourseView()
      }
    })
    const nav = document.querySelector(".course-views")
    const category = nav?.getAttribute("data-category-" + view)
    const breadcrumb = document.querySelector(".breadcrumb-container")
    if (breadcrumb) {
      breadcrumb.style.display = view === "26" && category && category !== nav?.getAttribute("data-category-25") ? "none" : ""
    }
    const tag = document.querySelector("article .course-tags .tag:first-child")
    if (category && tag) {
      tag.textContent = category.replace("/", "-")
      tag.classList.remove("tag-basic", "tag-required", "tag-advanced", "tag-practice", "tag-elective-basic", "tag-elective-practice")
      const classes = { "专业基础": "tag-basic", "专业必修": "tag-required", "专业进阶": "tag-advanced", "实践教学": "tag-practice", "专业选修/应用基础类": "tag-elective-basic", "专业选修/实践拓展类": "tag-elective-practice" }
      if (classes[category]) tag.classList.add(classes[category])
    }
  }
  document.addEventListener("nav", syncCourseView)
  syncCourseView()
`;

CourseViews.css = `
.course-views { width: 100%; min-height: 0; overflow: auto; }
.course-views h2 { font-size: 1rem; margin: 0 0 .6rem; }
.course-view-switch { display: flex; gap: .35rem; margin-bottom: .7rem; }
.course-view-switch button { flex: 1; cursor: pointer; border: 1px solid var(--gray); border-radius: .4rem; padding: .35rem; background: var(--light); color: var(--darkgray); }
.course-view-switch button[aria-pressed="true"] { background: var(--secondary); border-color: var(--secondary); color: var(--light); }
.course-view-panel[data-view="26"], [data-course-view="26"] .course-view-panel[data-view="25"] { display: none; }
[data-course-view="26"] .course-view-panel[data-view="26"] { display: block; }
.course-view-note { font-size: .83rem; line-height: 1.5; color: var(--darkgray); }
.course-view-group { margin: .7rem 0; }
.course-view-group summary { cursor: pointer; font-weight: 600; }
.course-view-group ul { list-style: none; padding-left: .8rem; margin: .35rem 0 .8rem; }
.course-view-group li { margin: .3rem 0; line-height: 1.35; font-size: .9rem; }
.course-view-group a[aria-current="page"] { font-weight: 700; color: var(--secondary); }
.course-view-unavailable { color: var(--gray); }
.course-view-unavailable small { display: block; }
.course-view-mobile { display: none; }
@media (max-width: 800px) {
  .sidebar.left:has(.course-views) { flex-wrap: wrap; }
  .course-view-desktop { display: none; }
  .course-view-mobile { display: block; width: 100%; }
  .course-view-mobile > summary { cursor: pointer; padding: .6rem 0; font-weight: 600; }
  .course-view-mobile nav { max-height: 70vh; overflow: auto; }
}
`;

export default CourseViews;

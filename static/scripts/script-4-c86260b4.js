
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

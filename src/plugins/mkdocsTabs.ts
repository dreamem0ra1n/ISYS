import type { QuartzTransformerPlugin } from "../../quartz/plugins/types";
import type { Element, ElementContent, Root } from "hast";

const tabHeading = /^===\s+"([^"]+)"\s*$/;
const tabsStartMarker = "isys-tabs-start";
const tabsEndMarker = "isys-tabs-end";
const tabStartPrefix = "isys-tab-start:";
const tabEndMarker = "isys-tab-end";

export function transformMkdocsTabs(source: string): string {
  const lines = source.split("\n");
  const output: string[] = [];
  let index = 0;

  while (index < lines.length) {
    const heading = tabHeading.exec(lines[index]);
    if (!heading) {
      output.push(lines[index]);
      index += 1;
      continue;
    }

    const tabs: Array<{ label: string; body: string[] }> = [];
    while (index < lines.length) {
      const currentHeading = tabHeading.exec(lines[index]);
      if (!currentHeading) break;
      index += 1;
      const body: string[] = [];
      while (index < lines.length && !tabHeading.test(lines[index])) {
        const line = lines[index];
        if (line === "" || line.startsWith("    ")) {
          body.push(line.startsWith("    ") ? line.slice(4) : line);
          index += 1;
          continue;
        }
        break;
      }
      tabs.push({ label: currentHeading[1], body });
    }

    output.push(`<!-- ${tabsStartMarker} -->`, "");
    for (const tab of tabs) {
      output.push(
        `<!-- ${tabStartPrefix}${encodeURIComponent(tab.label)} -->`,
        "",
      );
      output.push(...tab.body, "", `<!-- ${tabEndMarker} -->`, "");
    }
    output.push(`<!-- ${tabsEndMarker} -->`);
  }

  return output.join("\n");
}

function isComment(node: Root["children"][number], value: string): boolean {
  return (
    (node.type === "comment" && node.value.trim() === value) ||
    (node.type === "raw" && node.value === `<!-- ${value} -->`)
  );
}

function markerValue(node: Root["children"][number]): string | null {
  if (node.type === "comment") return node.value.trim();
  if (
    node.type === "raw" &&
    node.value.startsWith("<!-- ") &&
    node.value.endsWith(" -->")
  ) {
    return node.value.slice(5, -4);
  }
  return null;
}

function isWhitespace(node: Root["children"][number]): boolean {
  return node.type === "text" && /^\s*$/.test(node.value);
}

function createTabElement(
  label: string,
  children: ElementContent[],
  active: boolean,
): Element {
  return {
    type: "element",
    tagName: "div",
    properties: {
      className: ["isys-tab"],
      "data-tab-label": label,
      "data-active": String(active),
    },
    children,
  };
}

function rehypeIsysTabs() {
  return (tree: Root) => {
    const output: Root["children"] = [];
    let index = 0;
    while (index < tree.children.length) {
      if (!isComment(tree.children[index], tabsStartMarker)) {
        output.push(tree.children[index]);
        index += 1;
        continue;
      }

      index += 1;
      const tabs: Element[] = [];
      while (index < tree.children.length) {
        while (
          index < tree.children.length &&
          isWhitespace(tree.children[index])
        )
          index++;
        if (
          index >= tree.children.length ||
          isComment(tree.children[index], tabsEndMarker)
        )
          break;
        const marker = tree.children[index];
        const value = markerValue(marker);
        if (!value?.startsWith(tabStartPrefix)) break;
        const label = decodeURIComponent(
          value.slice(tabStartPrefix.length),
        ).replaceAll("&quot;", '"');
        index += 1;
        const body: ElementContent[] = [];
        while (
          index < tree.children.length &&
          !isComment(tree.children[index], tabEndMarker)
        ) {
          body.push(tree.children[index] as ElementContent);
          index += 1;
        }
        if (index >= tree.children.length) break;
        tabs.push(createTabElement(label, body, tabs.length === 0));
        index += 1;
      }

      if (
        index >= tree.children.length ||
        !isComment(tree.children[index], tabsEndMarker)
      ) {
        output.push(tree.children[index - 1]);
        continue;
      }
      output.push({
        type: "element",
        tagName: "div",
        properties: { className: ["isys-tabs"] },
        children: tabs,
      });
      index += 1;
    }
    tree.children = output;
  };
}

const MkdocsTabs: QuartzTransformerPlugin = () => ({
  name: "MkdocsTabs",
  textTransform: (_ctx, source) => transformMkdocsTabs(source),
  htmlPlugins: () => [rehypeIsysTabs],
  externalResources: () => ({
    css: [
      {
        inline: true,
        content: `
.isys-tabs { margin: 1rem 0; }
.isys-tab-buttons { display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: .75rem; }
.isys-tab-button { cursor: pointer; border: 1px solid var(--gray); border-radius: .4rem; padding: .35rem .75rem; background: var(--light); color: var(--darkgray); }
.isys-tab-button[aria-selected="true"] { border-color: var(--secondary); background: var(--secondary); color: var(--light); }
.isys-tab { display: none; }
.isys-tab[data-active="true"] { display: block; }
`,
      },
    ],
    js: [
      {
        loadTime: "afterDOMReady",
        contentType: "inline",
        spaPreserve: true,
        script: `
function initIsysTabs() {
  document.querySelectorAll(".isys-tabs").forEach((group) => {
    if (group.dataset.tabsReady === "true") return
    const tabs = Array.from(group.children).filter((child) => child.classList.contains("isys-tab"))
    if (!tabs.length) return
    tabs.forEach((tab, index) => {
      tab.dataset.active = String(index === 0)
    })
    if (tabs.length === 1) {
      group.dataset.tabsReady = "true"
      return
    }
    const buttons = document.createElement("div")
    buttons.className = "isys-tab-buttons"
    buttons.setAttribute("role", "tablist")
    tabs.forEach((tab, index) => {
      const button = document.createElement("button")
      button.type = "button"
      button.className = "isys-tab-button"
      button.textContent = tab.dataset.tabLabel || "选项 " + (index + 1)
      button.setAttribute("role", "tab")
      button.setAttribute("aria-selected", String(index === 0))
      button.onclick = () => tabs.forEach((item, tabIndex) => {
        item.dataset.active = String(tabIndex === index)
        buttons.children[tabIndex].setAttribute("aria-selected", String(tabIndex === index))
      })
      buttons.append(button)
    })
    group.prepend(buttons)
    group.dataset.tabsReady = "true"
  })
}
document.addEventListener("nav", initIsysTabs)
initIsysTabs()
`,
      },
    ],
  }),
});

export default MkdocsTabs;

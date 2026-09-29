import {
  loadQuartzConfig,
  loadQuartzLayout,
} from "./quartz/plugins/loader/config-loader"
import { componentRegistry } from "./quartz/components/registry"
import CourseViews from "./src/components/CourseViews"
import MkdocsTabs from "./src/plugins/mkdocsTabs"
import { PageTypes } from "./quartz/plugins"

componentRegistry.register("CourseViews", CourseViews, "local")
const config = await loadQuartzConfig()
config.plugins.transformers.push(MkdocsTabs())
const siteLayout = await loadQuartzLayout()
siteLayout.defaults.left = [...(siteLayout.defaults.left ?? []), CourseViews]
for (const pageType of Object.values(siteLayout.byPageType)) {
  pageType.left = [...(pageType.left ?? []), CourseViews]
}
const dispatcherIndex = config.plugins.emitters.findIndex(
  (emitter) => emitter.name === "PageTypeDispatcher",
)
config.plugins.emitters[dispatcherIndex] =
  PageTypes.PageTypeDispatcher(siteLayout)
export default config
export const layout = siteLayout

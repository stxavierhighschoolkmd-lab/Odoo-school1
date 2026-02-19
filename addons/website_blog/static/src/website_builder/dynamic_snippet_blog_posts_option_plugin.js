import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { KeepLast } from "@web/core/utils/concurrency";

/**
 * @typedef { Object } DynamicSnippetBlogPostsOptionShared
 * @property { DynamicSnippetBlogPostsOptionPlugin['fetchAuthors'] } fetchAuthors
 * @property { DynamicSnippetBlogPostsOptionPlugin['getModelNameFilter'] } getModelNameFilter
 */

export class DynamicSnippetBlogPostsOptionPlugin extends Plugin {
    static id = "dynamicSnippetBlogPostsOption";
    static dependencies = ["dynamicSnippetOption"];
    static shared = ["fetchAuthors", "getModelNameFilter"];
    modelNameFilter = "blog.post";
    /** @type {import("plugins").WebsiteResources} */
    resources = {
        on_snippet_dropped_handlers: this.onSnippetDropped.bind(this),
    };
    setup() {
        this.keepLast = new KeepLast();
    }
    getModelNameFilter() {
        return this.modelNameFilter;
    }
    async onSnippetDropped({ snippetEl }) {
        if (snippetEl.matches(".s_dynamic_snippet_blog_posts")) {
            await this.dependencies.dynamicSnippetOption.setOptionsDefaultValues(
                snippetEl,
                this.modelNameFilter
            );
        }
    }
    async fetchAuthors(searchString, selectedItems) {
        const websiteDomain = [...this._websiteDomain()];
        if (searchString) {
            websiteDomain.push(["author_name", "ilike", searchString]);
        }
        if (selectedItems && selectedItems.length) {
            websiteDomain.push(["author_id", "not in", selectedItems.map((item) => item.id)]);
        }

        const authors = await this.keepLast
            .add(
                this.services.orm.formattedReadGroup(
                    "blog.post",
                    websiteDomain,
                    ["author_id"],
                    [],
                    { limit: 10 }
                )
            )
            .then((results) =>
                results.map((r) => ({
                    id: r.author_id[0],
                    name: r.author_id[1],
                }))
            );

        return authors;
    }
    _websiteDomain() {
        const websiteId = this.services.website.currentWebsite.id;
        return ["|", ["website_id", "=", false], ["website_id", "=", websiteId]];
    }
}

registry
    .category("website-plugins")
    .add(DynamicSnippetBlogPostsOptionPlugin.id, DynamicSnippetBlogPostsOptionPlugin);

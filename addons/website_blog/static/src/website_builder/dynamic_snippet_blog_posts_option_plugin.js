import { setDatasetIfUndefined } from "@website/builder/plugins/options/dynamic_snippet_option_plugin";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

/**
 * @typedef { Object } DynamicSnippetBlogPostsOptionShared
 * @property { DynamicSnippetBlogPostsOptionPlugin['fetchBlogs'] } fetchBlogs
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
        this.authors = undefined;
    }
    getModelNameFilter() {
        return this.modelNameFilter;
    }
    async onSnippetDropped({ snippetEl }) {
        if (snippetEl.matches(".s_dynamic_snippet_blog_posts")) {
            setDatasetIfUndefined(snippetEl, "filterByAuthorId", -1);
            await this.dependencies.dynamicSnippetOption.setOptionsDefaultValues(
                snippetEl,
                this.modelNameFilter
            );
        }
    }

    async fetchAuthors() {
        if (!this.authors) {
            const websiteDomain = this._websiteDomain();
            this.authors = await this.services.orm
                .formattedReadGroup("blog.post", websiteDomain, ["author_id"], [])
                .then((results) =>
                    results.map((r) => ({ id: r.author_id[0], name: r.author_id[1] }))
                );
        }
        return this.authors;
    }

    _websiteDomain() {
        const websiteId = this.services.website.currentWebsite.id;
        return ["|", ["website_id", "=", false], ["website_id", "=", websiteId]];
    }
}

registry
    .category("website-plugins")
    .add(DynamicSnippetBlogPostsOptionPlugin.id, DynamicSnippetBlogPostsOptionPlugin);

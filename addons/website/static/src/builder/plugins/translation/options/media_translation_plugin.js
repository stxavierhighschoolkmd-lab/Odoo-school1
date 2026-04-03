import { BuilderAction } from "@html_builder/core/builder_action";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

/**
 * @typedef { Object } MediaTranslationShared
 * @property { MediaTranslationPlugin['translateMedia'] } translateMedia
 */

const translateImageOptionSelector = "img.o_savable_attribute";
const translateVideoOptionSelector = ".media_iframe_video.o_savable_attribute";
const translateDocumentOptionSelector = ".o_file_box";

export class MediaTranslationPlugin extends Plugin {
    static id = "mediaTranslation";
    static dependencies = ["history", "imagePostProcess", "media", "media_website", "translation"];
    static shared = ["translateMedia"];

    /** @type {import("plugins").WebsiteResources} */
    resources = {
        builder_actions: {
            TranslateMediaSrcAction,
        },
        builder_options_render_context: {
            translateImageOptionSelector,
            translateVideoOptionSelector,
            translateDocumentOptionSelector,
        },
        on_will_save_media_image_overrides: async (editingElement, newImgEl) => {
            // Replicate all attributes from the new image to the current
            // element, so that the translations are linked to the original
            // element on save.
            for (const attr of editingElement.attributes) {
                editingElement.removeAttribute(attr.localName);
            }
            for (const attr of newImgEl.attributes) {
                editingElement.setAttribute(attr.localName, attr.value);
            }
            const updateImageAttributes = await this.dependencies.imagePostProcess.processImage({
                img: editingElement,
                newDataset: { ...newImgEl.dataset },
            });
            updateImageAttributes();
            return true;
        },
    };

    setup() {
        this.savingMap = {
            images: this.saveImage.bind(this),
            videos: this.saveVideo.bind(this),
            documents: this.saveDocument.bind(this),
        };
        const translatableMediaSelector = [
            translateDocumentOptionSelector,
            translateImageOptionSelector,
            translateVideoOptionSelector,
        ].join(", ");

        this.addDomListener(this.editable, "dblclick", async (ev) => {
            const targetEl = ev.target.closest(translatableMediaSelector);
            if (!targetEl) {
                return;
            }
            if (this.isReplaceableMedia(targetEl)) {
                const mediaType = this.getMediaType(targetEl);
                this.dependencies.media_website.onDblClickEditableMedia(targetEl, async () => {
                    await this.translateMedia(targetEl, mediaType);
                });
            }
        });
        this.addDomListener(this.editable, "click", (ev) => {
            const targetEl = ev.target.closest(translatableMediaSelector);
            if (!targetEl) {
                return;
            }
            if (this.isReplaceableMedia(targetEl)) {
                this.dependencies.media_website.openImageTooltip(targetEl);
            }
        });
    }

    getMediaType(el) {
        if (el.matches(translateImageOptionSelector)) {
            return "images";
        }
        if (el.matches(translateVideoOptionSelector)) {
            return "videos";
        }
        if (el.matches(translateDocumentOptionSelector)) {
            return "documents";
        }
    }
    /**
     * @param {HTMLElement} mediaEl
     * @returns {Boolean}
     */
    isReplaceableMedia(mediaEl) {
        if (this.getMediaType(mediaEl) === "documents") {
            return true;
        }
        // An element marked `.o_translatable_attribute` means that it went
        // through `findOEditable` and `buildTranslationInfoMap` in the
        // TranslationPlugin. We can rely on that information.
        return mediaEl.classList.contains("o_translatable_attribute");
    }
    /**
     * Opens the media dialog to translate the source of the media.
     * @param {HTMLElement} element - element that should be "translated"
     * @param {"images" | "videos" | "documents"} mediaType
     */
    async translateMedia(element, mediaType) {
        await new Promise((resolve) => {
            const onClose = this.dependencies.media.openMediaDialog({
                onlyImages: mediaType === "images",
                noImages: mediaType !== "images",
                visibleTabs: [mediaType.toUpperCase()],
                node: element,
                // TODO @image-translate: this is a one-to-one "translation" of
                // the image. We bring back from the original image all the
                // manipulations that have been done: shape, resizing, filters..
                // But if the image is different, those options should also be
                // adaptable. We should have translation options to handle the
                // new image exactly like what is possible in the builder.
                copiedDataAttributes:
                    mediaType === "images" ? ["oeTranslationState", "resizeWidth", "glFilter"] : [],
                save: async (newMediaEl) => {
                    await this.savingMap[mediaType](element, newMediaEl);
                    this.dependencies.history.addStep(); // Needed for the dblclick
                },
            });
            onClose.then(resolve);
        });
    }
    /**
     * @param {HTMLElement} el - element whose attribute is translated
     * @param {string} translation - new translation
     * @param {string} originalText - text before the new translation
     * @param {string} attribute - attribute to update in the translation map
     */
    handleTranslationMapHistory(el, translation, originalText, attribute) {
        const updateTranslationMap = this.dependencies.translation.updateTranslationMap;
        this.dependencies.history.applyCustomMutation({
            apply: () => {
                updateTranslationMap(el, translation, attribute);
            },
            revert: () => {
                updateTranslationMap(el, originalText, attribute);
            },
        });
    }

    async saveImage(editingElement) {
        const elTranslationInfo = this.dependencies.translation.getTranslationInfo(editingElement);
        const originalSrc = elTranslationInfo.src.translation;
        const originalSrcset = elTranslationInfo.srcset?.translation;
        const translatedSrc = editingElement.getAttribute("src");
        this.handleTranslationMapHistory(editingElement, translatedSrc, originalSrc, "src");
        if (originalSrcset) {
            // Hack: we don't have the new srcset yet (it's computed on save).
            // Instead, register a dummy change (empty string) to update its
            // translation later on save.
            this.handleTranslationMapHistory(editingElement, "", originalSrcset, "srcset");
        }
        editingElement.classList.add("oe_translated");
        this.trigger("on_media_replaced_handlers", { newMediaEl: editingElement });
    }

    saveVideo(editingElement, newVideoEl) {
        const originalSrc =
            this.dependencies.translation.getTranslationInfo(editingElement)["data-oe-expression"]
                .translation;
        const newSrc = newVideoEl.querySelector("iframe").getAttribute("src");
        editingElement.setAttribute("data-oe-expression", newSrc);
        editingElement.querySelector("iframe").setAttribute("src", newSrc);
        editingElement.classList.add("oe_translated");

        this.handleTranslationMapHistory(editingElement, newSrc, originalSrc, "data-oe-expression");
    }

    saveDocument(editingElement, newFileEl) {
        editingElement.replaceChildren(...newFileEl.children);
        editingElement.dataset.attachmentId = newFileEl.dataset.attachmentId;
        editingElement.querySelector("a.o_link_readonly").classList.add("o_translate_inline");
    }
}

registry.category("translation-plugins").add(MediaTranslationPlugin.id, MediaTranslationPlugin);

export class TranslateMediaSrcAction extends BuilderAction {
    static id = "translateMediaSrc";
    static dependencies = ["mediaTranslation"];

    async apply({ editingElement, params: { mainParam: mediaType } }) {
        await this.dependencies.mediaTranslation.translateMedia(editingElement, mediaType);
    }
}
